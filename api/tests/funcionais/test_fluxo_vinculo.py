import uuid

import pytest

ADMIN = {"X-Admin-Key": "admin-teste"}


def _torre(cliente, kit="pro"):
    torre_id = "AT-" + uuid.uuid4().hex[:12].upper()
    r = cliente.post("/admin/torres", json={"torreId": torre_id, "kit": kit}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return torre_id, r.json()["codigoAtivacao"]


def _login(cliente, nome):
    r = cliente.post("/auth/dev", json={"id": nome})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()


def test_vincular_exige_login(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    _, codigo = _torre(cliente)
    # Antes: bastava mandar qualquer e-mail no corpo.
    r = cliente.post("/torre/vincular", json={"email": "vitima@x.com", "token_torre": codigo})
    assert r.status_code == 401


def test_codigo_inventado_nao_vale(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    h, _ = _login(cliente, "ze")
    assert cliente.post("/torre/vincular", json={"token_torre": "minha-torre"}, headers=h).status_code == 400
    assert cliente.post("/torre/vincular", json={"codigo": "ABCD-EFGH"}, headers=h).status_code == 400


def test_regras_um_para_um_e_eventos(cliente_e_eventos):
    cliente, eventos = cliente_e_eventos
    t1, c1 = _torre(cliente)
    t2, c2 = _torre(cliente, "basico")
    assert [e[0] for e in eventos[-2:]] == ["torre.cadastrada", "torre.cadastrada"]

    maria, login = _login(cliente, "maria")
    assert login["possui_torre"] is False and login["token"]

    r = cliente.post("/torre/vincular", json={"codigo": c1.lower().replace("-", ""), "apelido": "Varanda"},
                     headers=maria)
    assert r.status_code == 200 and r.json()["torre_id"] == t1
    tipo, estado = eventos[-1]
    assert tipo == "torre.vinculada" and estado["donoId"] == "dev:maria" and estado["versao"] == 2

    # repetir o pedido nao gera erro nem evento
    n = len(eventos)
    assert cliente.post("/torre/vincular", json={"codigo": c1}, headers=maria).status_code == 200
    assert len(eventos) == n

    # Regra 1: Maria ja tem uma torre
    r = cliente.post("/torre/vincular", json={"codigo": c2}, headers=maria)
    assert r.status_code == 400 and "já possui" in r.json()["detail"]

    # Regra 2: torre da Maria nao vai para o Joao
    joao, _ = _login(cliente, "joao")
    assert cliente.post("/torre/vincular", json={"codigo": c1}, headers=joao).status_code == 409

    # login de novo informa a torre (campos que o app usa)
    _, login = _login(cliente, "maria")
    assert login["possui_torre"] is True and login["torre_id"] == t1

    # Maria desvincula; o mesmo adesivo passa a valer para o Joao
    assert cliente.delete(f"/torre/{t1}/vinculo", headers=maria).status_code == 200
    assert eventos[-1][0] == "torre.desvinculada" and eventos[-1][1]["donoId"] is None
    assert cliente.post("/torre/vincular", json={"codigo": c1}, headers=joao).status_code == 200


def test_rabbitmq_fora_desfaz_o_vinculo(cliente_e_eventos, monkeypatch):
    import eventos as modulo
    cliente, _ = cliente_e_eventos
    t, c = _torre(cliente)
    h, _ = _login(cliente, "lia")

    def falha(tipo, torre):
        raise modulo.FalhaAoPublicar("broker fora")
    monkeypatch.setattr(modulo, "publicar", falha)
    assert cliente.post("/torre/vincular", json={"codigo": c}, headers=h).status_code == 503
    assert cliente.get("/auth/me", headers=h).json()["torres"] == []


def test_admin_protegido_e_validado(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    assert cliente.post("/admin/torres", json={"torreId": "AT-123456", "kit": "pro"}).status_code == 403
    assert cliente.post("/admin/torres", json={"torreId": "../x", "kit": "pro"}, headers=ADMIN).status_code == 422
    assert cliente.post("/admin/torres", json={"torreId": "AT-123456", "kit": "ultra"}, headers=ADMIN).status_code == 422


@pytest.mark.parametrize("aud,esperado", [("outro-app.apps.googleusercontent.com", 401),
                                          ("nosso-app.apps.googleusercontent.com", 200)])
def test_google_confere_o_app_do_token(cliente_e_eventos, monkeypatch, aud, esperado):
    from google.oauth2 import id_token
    cliente, _ = cliente_e_eventos
    monkeypatch.setattr(id_token, "verify_oauth2_token", lambda t, r: {
        "iss": "https://accounts.google.com", "aud": aud, "sub": "123", "email": "m@x.com",
        "email_verified": True, "name": "Maria"})
    r = cliente.post("/auth/google", json={"token": "a.b.c"})
    assert r.status_code == esperado


@pytest.mark.parametrize("aud,esperado", [("outro-app.apps.googleusercontent.com", 401),
                                          ("nosso-app.apps.googleusercontent.com", 200)])
def test_access_token_da_web_tambem_confere_o_app(cliente_e_eventos, monkeypatch, aud, esperado):
    import google_auth
    cliente, _ = cliente_e_eventos

    class Resp:
        def __init__(self, codigo, corpo):
            self.status_code, self._corpo = codigo, corpo

        def json(self):
            return self._corpo

    def falso_get(url, **kw):
        if "tokeninfo" in url:
            return Resp(200, {"aud": aud, "azp": aud, "sub": "999", "email": "w@x.com",
                              "email_verified": "true"})
        return Resp(200, {"name": "Web"})
    monkeypatch.setattr(google_auth.requests, "get", falso_get)
    assert cliente.post("/auth/google", json={"token": "ya29.token-de-acesso"}).status_code == esperado
