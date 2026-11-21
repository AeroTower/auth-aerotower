"""Testes unitarios da verificacao de tokens do Google (rede trocada por dubles)."""
import pytest

import google_auth
from google_auth import TokenGoogleInvalido, verificar

NOSSO = {"nosso-app.apps.googleusercontent.com"}


class Resposta:
    def __init__(self, codigo, corpo):
        self.status_code, self._corpo = codigo, corpo

    def json(self):
        return self._corpo


def _id_token(monkeypatch, dados=None, erro=None):
    def falso(token, requisicao):
        if erro:
            raise erro
        return dados
    monkeypatch.setattr(google_auth.id_token, "verify_oauth2_token", falso)


def _tokeninfo(monkeypatch, codigo=200, corpo=None, userinfo=None):
    def falso_get(url, **kw):
        if "tokeninfo" in url:
            if isinstance(corpo, Exception):
                raise corpo
            return Resposta(codigo, corpo or {})
        if isinstance(userinfo, Exception):
            raise userinfo
        return userinfo or Resposta(500, {})
    monkeypatch.setattr(google_auth.requests, "get", falso_get)


BASE_ID = {"iss": "accounts.google.com", "aud": "nosso-app.apps.googleusercontent.com",
           "sub": "123", "email": "m@x.com", "email_verified": True, "name": "Maria"}


def test_servidor_sem_client_id_recusa_tudo():
    with pytest.raises(TokenGoogleInvalido, match="GOOGLE_CLIENT_IDS"):
        verificar("a.b.c", [])


def test_id_token_valido_devolve_a_conta(monkeypatch):
    _id_token(monkeypatch, BASE_ID)
    conta = verificar(" a.b.c ", NOSSO)
    assert (conta.sub, conta.email, conta.nome) == ("123", "m@x.com", "Maria")


@pytest.mark.parametrize("mudanca, motivo", [
    ({"iss": "https://falso.com"}, "Emissor"),
    ({"aud": "outro-app"}, "outro aplicativo"),
    ({"email_verified": "false"}, "não verificado"),
])
def test_id_token_recusado(monkeypatch, mudanca, motivo):
    _id_token(monkeypatch, {**BASE_ID, **mudanca})
    with pytest.raises(TokenGoogleInvalido, match=motivo):
        verificar("a.b.c", NOSSO)


def test_id_token_com_assinatura_ruim(monkeypatch):
    _id_token(monkeypatch, erro=ValueError("Wrong number of segments"))
    with pytest.raises(TokenGoogleInvalido, match="ID token recusado"):
        verificar("a.b.c", NOSSO)


def test_access_token_valido_pega_o_nome_no_userinfo(monkeypatch):
    _tokeninfo(monkeypatch, corpo={"aud": "x", "azp": "nosso-app.apps.googleusercontent.com",
                                   "sub": "9", "email": "w@x.com", "email_verified": "true"},
               userinfo=Resposta(200, {"name": "Web"}))
    conta = verificar("ya29.abc", NOSSO)
    assert conta.sub == "9" and conta.nome == "Web"


def test_userinfo_fora_do_ar_nao_impede_o_login(monkeypatch):
    _tokeninfo(monkeypatch, corpo={"aud": "nosso-app.apps.googleusercontent.com", "sub": "9"},
               userinfo=google_auth.requests.ConnectionError("fora"))
    assert verificar("ya29.abc", NOSSO).nome is None


@pytest.mark.parametrize("codigo, corpo, motivo", [
    (400, {}, "inválido ou expirado"),
    (200, {"aud": "nosso-app.apps.googleusercontent.com"}, "falta o escopo"),
    (200, {"aud": "nosso-app.apps.googleusercontent.com", "sub": "9", "email": "a@b.c",
           "email_verified": "false"}, "não verificado"),
])
def test_access_token_recusado(monkeypatch, codigo, corpo, motivo):
    _tokeninfo(monkeypatch, codigo, corpo)
    with pytest.raises(TokenGoogleInvalido, match=motivo):
        verificar("ya29.abc", NOSSO)


def test_google_fora_do_ar(monkeypatch):
    _tokeninfo(monkeypatch, corpo=google_auth.requests.Timeout("lento"))
    with pytest.raises(TokenGoogleInvalido, match="indisponível"):
        verificar("ya29.abc", NOSSO)
