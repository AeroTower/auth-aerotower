"""Confere tokens do Google.

O app manda um de dois tipos:
* celular: ID token (um JWT assinado pelo Google);
* web: access token (google_sign_in na web nao entrega ID token).

Nos dois casos a regra que importa e a mesma: o token tem de ter sido
emitido para UM DOS NOSSOS client IDs. Sem essa checagem, o token de
qualquer outro site com "Entrar com Google" serviria para entrar aqui.
"""
import logging
from dataclasses import dataclass
from typing import Iterable, Optional

import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

logger = logging.getLogger(__name__)

_EMISSORES = {"accounts.google.com", "https://accounts.google.com"}
_TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"


class TokenGoogleInvalido(Exception):
    pass


@dataclass
class ContaGoogle:
    sub: str
    email: Optional[str]
    nome: Optional[str]


def _verdadeiro(valor) -> bool:
    return valor is True or str(valor).lower() == "true"


def verificar(token: str, client_ids: Iterable[str]) -> ContaGoogle:
    client_ids = set(client_ids)
    if not client_ids:
        raise TokenGoogleInvalido("Servidor sem GOOGLE_CLIENT_IDS configurado.")
    token = (token or "").strip()
    if token.count(".") == 2:
        return _verificar_id_token(token, client_ids)
    return _verificar_access_token(token, client_ids)


def _verificar_id_token(token: str, client_ids: set) -> ContaGoogle:
    try:
        dados = id_token.verify_oauth2_token(token, google_requests.Request())
    except Exception as erro:
        raise TokenGoogleInvalido(f"ID token recusado: {erro}")
    if dados.get("iss") not in _EMISSORES:
        raise TokenGoogleInvalido("Emissor não é o Google.")
    if dados.get("aud") not in client_ids:
        raise TokenGoogleInvalido("Token emitido para outro aplicativo.")
    if dados.get("email") and not _verdadeiro(dados.get("email_verified", True)):
        raise TokenGoogleInvalido("E-mail não verificado.")
    return ContaGoogle(sub=dados["sub"], email=dados.get("email"), nome=dados.get("name"))


def _verificar_access_token(token: str, client_ids: set) -> ContaGoogle:
    try:
        resposta = requests.get(_TOKENINFO, params={"access_token": token}, timeout=10)
    except requests.RequestException as erro:
        raise TokenGoogleInvalido(f"Google indisponível: {erro}")
    if resposta.status_code != 200:
        raise TokenGoogleInvalido("Access token inválido ou expirado.")
    dados = resposta.json()
    if dados.get("aud") not in client_ids and dados.get("azp") not in client_ids:
        raise TokenGoogleInvalido("Token emitido para outro aplicativo.")
    if not dados.get("sub"):
        raise TokenGoogleInvalido("Token sem identificação da conta (falta o escopo openid/email).")
    if dados.get("email") and not _verdadeiro(dados.get("email_verified")):
        raise TokenGoogleInvalido("E-mail não verificado.")

    nome = None
    try:  # so para mostrar o nome; nao decide nada
        info = requests.get("https://www.googleapis.com/oauth2/v3/userinfo",
                            headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if info.status_code == 200:
            nome = info.json().get("name")
    except requests.RequestException:
        pass
    return ContaGoogle(sub=dados["sub"], email=dados.get("email"), nome=nome)
