"""Token de sessao do AeroTower.

Emitido aqui, validado aqui e no Backend (mesmo JWT_SEGREDO). Leva so o
necessario: quem e a pessoa. Quais torres ela tem, o Backend sabe pelos
eventos — assim desvincular uma torre vale na hora, sem esperar o token
expirar.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from config import JWT_AUDIENCIA, JWT_EMISSOR, JWT_SEGREDO, JWT_VALIDADE_DIAS

logger = logging.getLogger(__name__)

if not JWT_SEGREDO:
    logger.warning("JWT_SEGREDO vazio: usando um aleatório (o Backend não vai aceitar estes tokens).")
_SEGREDO = JWT_SEGREDO or secrets.token_urlsafe(48)


class SessaoInvalida(Exception):
    pass


def emitir(usuario_id: str, email: str = None) -> str:
    agora = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": usuario_id, "email": email,
            "iss": JWT_EMISSOR, "aud": JWT_AUDIENCIA,
            "iat": agora, "exp": agora + timedelta(days=JWT_VALIDADE_DIAS),
        },
        _SEGREDO, algorithm="HS256",
    )


def validar(token: str) -> str:
    try:
        dados = jwt.decode(token, _SEGREDO, algorithms=["HS256"], issuer=JWT_EMISSOR,
                           audience=JWT_AUDIENCIA, options={"require": ["sub", "exp"]})
    except jwt.ExpiredSignatureError:
        raise SessaoInvalida("Sessão expirada. Entre de novo.")
    except jwt.PyJWTError:
        raise SessaoInvalida("Sessão inválida. Entre de novo.")
    return dados["sub"]
