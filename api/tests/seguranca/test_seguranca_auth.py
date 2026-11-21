"""Testes de seguranca do servico de auth: ataques e acessos indevidos."""
import jwt
import pytest

import codigo
import main
from apoio import ADMIN, login, nova_torre
from banco import SessionLocal, Torre


def test_banco_guarda_so_o_hash_do_codigo(cliente_e_eventos):
    """Vazou o banco? O codigo do adesivo nao esta la."""
    cliente, _ = cliente_e_eventos
    torre, cod = nova_torre(cliente)
    with SessionLocal() as s:
        guardado = s.get(Torre, torre).codigo_hash
    assert cod not in guardado and codigo.normalizar(cod) not in guardado
    assert guardado == codigo.hash_de(cod) and len(guardado) == 64


def test_codigo_errado_nao_revela_se_a_torre_existe(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    h, _ = login(cliente)
    formato_ruim = cliente.post("/torre/vincular", json={"codigo": "123"}, headers=h).json()
    nao_existe = cliente.post("/torre/vincular", json={"codigo": "ABCD-EFGH"}, headers=h).json()
    assert formato_ruim == nao_existe == {"detail": "Código de ativação inválido."}


def test_tentativa_de_adivinhar_codigo(cliente_e_eventos):
    """Forca bruta: 200 palpites seguidos nao acertam nenhum adesivo."""
    cliente, eventos = cliente_e_eventos
    nova_torre(cliente)
    h, _ = login(cliente)
    n = len(eventos)
    acertos = sum(cliente.post("/torre/vincular", json={"codigo": codigo.gerar()}, headers=h).status_code == 200
                  for _ in range(200))
    assert acertos == 0 and len(eventos) == n


def test_token_assinado_com_outro_segredo(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    falso = jwt.encode({"sub": "dev:ana", "iss": "aerotower-auth", "aud": "aerotower", "exp": 9999999999},
                       "segredo-chutado", algorithm="HS256")
    assert cliente.get("/auth/me", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_sem_token_nao_entra(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    assert cliente.get("/auth/me").status_code == 401


def test_chave_de_admin_errada(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    for chave in ["", "admin", "ADMIN-TESTE", "admin-teste "]:
        assert cliente.get("/admin/torres", headers={"X-Admin-Key": chave}).status_code == 403


def test_rotas_de_admin_desligadas_sem_chave_configurada(cliente_e_eventos, monkeypatch):
    cliente, _ = cliente_e_eventos
    monkeypatch.setattr(main, "ADMIN_API_KEY", "")
    assert cliente.get("/admin/torres", headers=ADMIN).status_code == 403


def test_login_sem_google_some_em_producao(cliente_e_eventos, monkeypatch):
    cliente, _ = cliente_e_eventos
    monkeypatch.setattr(main, "AUTH_MODO_DEV", False)
    assert cliente.post("/auth/dev", json={"id": "ana"}).status_code == 404


@pytest.mark.parametrize("identificador", ["ana'; DROP TABLE usuarios;--", "<script>", "a" * 65, "", "../x"])
def test_login_dev_recusa_caracteres_perigosos(cliente_e_eventos, identificador):
    cliente, _ = cliente_e_eventos
    assert cliente.post("/auth/dev", json={"id": identificador}).status_code == 422


def test_ninguem_desvincula_torre_alheia(cliente_e_eventos):
    cliente, eventos = cliente_e_eventos
    torre, cod = nova_torre(cliente)
    dona, _ = login(cliente)
    cliente.post("/torre/vincular", json={"codigo": cod}, headers=dona)
    intruso, _ = login(cliente)
    n = len(eventos)
    assert cliente.delete(f"/torre/{torre}/vinculo", headers=intruso).status_code == 404
    assert len(eventos) == n
    assert [t["id"] for t in cliente.get("/auth/me", headers=dona).json()["torres"]] == [torre]


def test_apelido_gigante_e_recusado(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    _, cod = nova_torre(cliente)
    h, _ = login(cliente)
    assert cliente.post("/torre/vincular", json={"codigo": cod, "apelido": "x" * 41},
                        headers=h).status_code == 422
