import os
import json
import requests
import pika
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

app = FastAPI(title="AeroTower API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")

# Dicionário de estado (Substitua por consulta SQL/PostgreSQL no futuro)
db_torres = {}

class TokenSchema(BaseModel):
    token: str

class VincularTorreSchema(BaseModel):
    email: str
    token_torre: str

def publicar_no_rabbitmq(payload: dict):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue='vincular_torre', durable=True)
        channel.basic_publish(
            exchange='',
            routing_key='vincular_torre',
            body=json.dumps(payload),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
    except Exception as e:
        print(f"=== [ERRO RABBITMQ] {e} ===", flush=True)

@app.post("/auth/google")
def auth_google(data: TokenSchema):
    token = data.token
    user_email = None

    try:
        id_info = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        user_email = id_info.get("email")
    except Exception:
        pass

    if not user_email:
        try:
            resp = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={"Authorization": f"Bearer {token}"}, timeout=10)
            if resp.status_code == 200:
                user_email = resp.json().get("email")
        except Exception:
            pass

    if not user_email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token do Google inválido")

    # Verifica se o e-mail já possui torre vinculada
    possui_torre = user_email in db_torres

    return {
        "status": "success",
        "email": user_email,
        "possui_torre": possui_torre,
        "torre_id": db_torres.get(user_email)
    }

@app.post("/torre/vincular")
def vincular_torre(data: VincularTorreSchema):
    email = data.email.strip()
    token_torre = data.token_torre.strip()

    # REGRA DE NEGÓCIO 1: Usuário já tem torre?
    if email in db_torres:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"O e-mail '{email}' já possui a torre '{db_torres[email]}' vinculada."
        )

    # REGRA DE NEGÓCIO 2: Torre já pertence a outro usuário?
    if token_torre in db_torres.values():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A AeroTower '{token_torre}' já está associada a outro usuário."
        )

    # Salva o vínculo
    db_torres[email] = token_torre

    # Publica evento para o Worker iniciar rotinas de telemetria/MQTT
    publicar_no_rabbitmq({
        "evento": "TORRE_VINCULADA",
        "email": email,
        "token_torre": token_torre
    })

    return {
        "status": "success",
        "message": "Torre vinculada com sucesso!",
        "email": email,
        "torre_id": token_torre
    }