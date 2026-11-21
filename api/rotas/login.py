import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import google_auth
from banco import Usuario, get_db
from config import AUTH_MODO_DEV, GOOGLE_CLIENT_IDS
from contas import resposta_login, salvar_usuario
from dependencias import usuario_logado
from erros import LoginRecusado, RotaDesligada
from regras_torre import torres_do_usuario
from schemas import LoginDevSchema, TokenSchema

logger = logging.getLogger("auth")
router = APIRouter(tags=["Login"])


@router.post("/auth/google")
def auth_google(data: TokenSchema, db: Session = Depends(get_db)):
    try:
        conta = google_auth.verificar(data.token, GOOGLE_CLIENT_IDS)
    except google_auth.TokenGoogleInvalido as erro:
        logger.info("Login Google recusado: %s", erro)
        raise LoginRecusado("Token do Google inválido") from erro
    usuario = salvar_usuario(db, conta.sub, conta.email, conta.nome)
    return resposta_login(db, usuario)


@router.post("/auth/dev", summary="Login sem Google (só com AUTH_MODO_DEV=true)")
def auth_dev(data: LoginDevSchema, db: Session = Depends(get_db)):
    if not AUTH_MODO_DEV:
        raise RotaDesligada()
    identificador = data.id.strip()
    usuario = salvar_usuario(db, f"dev:{identificador}", f"{identificador}@dev.local", identificador)
    return resposta_login(db, usuario)


@router.get("/auth/me")
def eu(usuario: Usuario = Depends(usuario_logado), db: Session = Depends(get_db)):
    return {
        "usuario": {"id": usuario.id, "email": usuario.email, "nome": usuario.nome},
        "torres":  [{"id": t.id, "kit": t.kit, "apelido": t.apelido}
                    for t in torres_do_usuario(db, usuario.id)],
    }
