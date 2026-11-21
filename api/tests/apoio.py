"""Funcoes de apoio dos testes da API."""
import uuid

ADMIN = {"X-Admin-Key": "admin-teste"}


def nova_torre(cliente, kit="pro"):
    torre_id = "AT-" + uuid.uuid4().hex[:12].upper()
    r = cliente.post("/admin/torres", json={"torreId": torre_id, "kit": kit}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return torre_id, r.json()["codigoAtivacao"]


def login(cliente, nome=None):
    nome = nome or f"u{uuid.uuid4().hex[:8]}"
    r = cliente.post("/auth/dev", json={"id": nome})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()
