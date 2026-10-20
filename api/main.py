from fastapi import FastAPI, HTTPException, status
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import pika
import json
import os

app = FastAPI()

# Substitua pelo seu Client ID gerado no Google Cloud Console
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "seu-client-id-do-google.apps.googleusercontent.com")

def publicar_na_fila(dados):
    host = os.getenv("RABBITMQ_HOST", "localhost")
    conexao = pika.BlockingConnection(pika.ConnectionParameters(host=host))
    canal = conexao.channel()
    
    # Declara uma fila durável para garantir que as mensagens não se perdem se o RabbitMQ reiniciar
    canal.queue_declare(queue='fila_vinculo_torre', durable=True)
    
    canal.basic_publish(
        exchange='',
        routing_key='fila_vinculo_torre',
        body=json.dumps(dados),
        properties=pika.BasicProperties(delivery_mode=2) # Torna a mensagem persistente
    )
    conexao.close()

@app.post("/auth/google")
def autenticar_google(token_google: str):
    try:
        # Valida o token de ID enviado pelo cliente diretamente com o Google
        idinfo = id_token.verify_oauth2_token(token_google, google_requests.Request(), GOOGLE_CLIENT_ID)
        
        user_email = idinfo.get('email')
        user_name = idinfo.get('name')
        
        return {
            "status": "sucesso", 
            "mensagem": f"Bem-vindo ao sistema da Hidroponia, {user_name}!", 
            "email": user_email
        }
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token do Google inválido ou expirado."
        )

@app.post("/torre/vincular")
def vincular_torre(token_google: str, tower_id: str):
    # 1. Valida a identidade do utilizador via Google Auth antes de permitir o vínculo da torre
    try:
        idinfo = id_token.verify_oauth2_token(token_google, google_requests.Request(), GOOGLE_CLIENT_ID)
        user_email = idinfo.get('email')
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação falhou. Token inválido."
        )
    
    # 2. Publica o evento de pareamento (QR Code da hidroponia) na fila do RabbitMQ
    evento = {
        "user_email": user_email,
        "tower_id": tower_id
    }
    publicar_na_fila(evento)
    
    return {
        "status": "processando", 
        "mensagem": f"Solicitação de vínculo da torre {tower_id} enviada para processamento em background!"
    }