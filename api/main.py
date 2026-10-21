import os
import requests
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

# ------------------------------------------------------------------------------
# Banco de Dados Simulado (Substitua pelas suas consultas SQL/ORM)
# Estrutura: { "email_usuario": "token_da_torre" }
# ------------------------------------------------------------------------------
db_torres = {}


# ------------------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------------------
class TokenSchema(BaseModel):
    token: str

class VincularTorreSchema(BaseModel):
    email: str
    token_torre: str


# ------------------------------------------------------------------------------
# Rotas
# ------------------------------------------------------------------------------
@app.post("/auth/google")
def auth_google(data: TokenSchema):
    token = data.token
    user_email = None

    # 1. Tenta validar como ID Token (JWT)
    try:
        id_info = id_token.verify_oauth2_token(
            token, google_requests.Request(), GOOGLE_CLIENT_ID
        )
        user_email = id_info.get("email")
    except Exception:
        pass

    # 2. Tenta validar como Access Token (Google UserInfo API)
    if not user_email:
        try:
            userinfo_response = requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            if userinfo_response.status_code == 200:
                user_email = userinfo_response.json().get("email")
        except Exception:
            pass

    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token do Google inválido ou não autorizado"
        )

    # REGRA DE NEGÓCIO: Checa se este e-mail já tem uma torre associada
    torre_vinculada = db_torres.get(user_email)
    possui_torre = torre_vinculada is not None

    return {
        "status": "success",
        "email": user_email,
        "possui_torre": possui_torre,
        "torre_id": torre_vinculada
    }


@app.post("/torre/vincular")
def vincular_torre(data: VincularTorreSchema):
    email = data.email.strip()
    token_torre = data.token_torre.strip()

    if not email or not token_torre:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail e token da torre são obrigatórios."
        )

    # REGRA DE NEGÓCIO 1: Usuário já possui uma torre?
    if email in db_torres:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"O usuário '{email}' já possui a torre '{db_torres[email]}' vinculada."
        )

    # REGRA DE NEGÓCIO 2: A torre já está vinculada a outro usuário?
    if token_torre in db_torres.values():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta AeroTower já está associada a outro usuário."
        )

    # Registra o vínculo único
    db_torres[email] = token_torre
    print(f"=== [BANCO] Novo vínculo criado: {email} <-> {token_torre} ===", flush=True)

    return {
        "status": "success",
        "message": "AeroTower vinculada com sucesso!",
        "email": email,
        "torre_id": token_torre
    }