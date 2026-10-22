"""Configuracao do Servico A. Tudo vem do ambiente (.env no docker-compose)."""
import os

from dotenv import load_dotenv

load_dotenv()


def _lista(nome: str):
    return [v.strip() for v in os.getenv(nome, "").split(",") if v.strip()]


# Client IDs OAuth aceitos (web, Android, iOS). Aceita o nome antigo
# GOOGLE_CLIENT_ID para nao quebrar o .env de quem ja tinha.
GOOGLE_CLIENT_IDS = _lista("GOOGLE_CLIENT_IDS") or _lista("GOOGLE_CLIENT_ID")

# Token de sessao: o MESMO segredo vai no Backend, que so valida.
JWT_SEGREDO       = os.getenv("JWT_SEGREDO", "")
JWT_EMISSOR       = "aerotower-auth"
JWT_AUDIENCIA     = "aerotower"
JWT_VALIDADE_DIAS = int(os.getenv("JWT_VALIDADE_DIAS", "7"))

_db = (os.getenv("DATABASE_URL") or "sqlite:///./auth.db").strip()
DATABASE_URL = _db.replace("postgres://", "postgresql://", 1) if _db.startswith("postgres://") else _db

# Aceita RABBITMQ_URL completo (CloudAMQP, Azure) ou so o host (docker-compose antigo).
RABBITMQ_URL = os.getenv("RABBITMQ_URL") or f"amqp://guest:guest@{os.getenv('RABBITMQ_HOST', 'localhost')}:5672/%2F"
EXCHANGE     = os.getenv("RABBITMQ_EXCHANGE", "aerotower.eventos")

# Regra de negocio: quantas torres uma pessoa pode ter. 1 = regra atual.
MAX_TORRES_POR_USUARIO = int(os.getenv("MAX_TORRES_POR_USUARIO", "1"))

# true libera POST /auth/dev (login sem Google, para desenvolver). Nunca em producao.
AUTH_MODO_DEV = os.getenv("AUTH_MODO_DEV", "false").strip().lower() in ("1", "true", "sim")

# Chave das rotas /admin (script de fabrica). Vazia = rotas desligadas.
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

# Origens do app e da loja. "*" so em desenvolvimento.
CORS_ORIGENS = _lista("CORS_ORIGENS") or ["*"]
