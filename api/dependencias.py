"""Dependencias das rotas: quem esta logado e a chave de admin."""
import secrets
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

import sessao
from banco import Usuario, get_db
from config import ADMIN_API_KEY

# HTTPBearer (e nao um Header "authorization") faz o /docs mostrar o botao
# Authorize: o Swagger ignora parametro de cabecalho chamado Authorization.
_bearer = HTTPBearer(auto_error=False, description="Token de sessão (campo `token` do /auth/google ou /auth/dev)")


def usuario_logado(
    credenciais: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    if credenciais is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Faça login para continuar.")
    try:
        usuario_id = sessao.validar(credenciais.credentials.strip())
    except sessao.SessaoInvalida as erro:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(erro)) from erro
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário não encontrado. Entre de novo.")
    return usuario


def exigir_admin(x_admin_key: Optional[str] = Header(default=None)) -> None:
    if not ADMIN_API_KEY:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Rotas de admin desligadas (ADMIN_API_KEY vazia).")
    if not x_admin_key or not secrets.compare_digest(x_admin_key, ADMIN_API_KEY):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Chave de admin inválida.")
