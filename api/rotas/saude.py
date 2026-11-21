from fastapi import APIRouter

from config import GOOGLE_CLIENT_IDS, MAX_TORRES_POR_USUARIO

router = APIRouter(tags=["Saúde"])


@router.get("/")
def home():
    return {
        "servico": "auth-aerotower",
        "status": "online",
        "google_configurado": bool(GOOGLE_CLIENT_IDS),
        "max_torres_por_usuario": MAX_TORRES_POR_USUARIO,
    }
