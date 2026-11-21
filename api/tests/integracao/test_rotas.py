"""Testes de integracao: rotas da API + banco SQLite (RabbitMQ trocado por duble)."""
import eventos as modulo_eventos
import regras_torre
from apoio import ADMIN, login, nova_torre


def test_home_informa_configuracao(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    corpo = cliente.get("/").json()
    assert corpo["status"] == "online" and corpo["google_configurado"] is True
    assert corpo["max_torres_por_usuario"] == 1


def test_auth_me_lista_as_torres_da_pessoa(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    torre, codigo = nova_torre(cliente, "completo")
    h, _ = login(cliente, "rita")
    cliente.post("/torre/vincular", json={"codigo": codigo, "apelido": "  Cozinha  "}, headers=h)
    eu = cliente.get("/auth/me", headers=h).json()
    assert eu["usuario"]["email"] == "rita@dev.local"
    assert eu["torres"] == [{"id": torre, "kit": "completo", "apelido": "Cozinha"}]


def test_campo_antigo_token_torre_ainda_funciona(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    torre, codigo = nova_torre(cliente)
    h, _ = login(cliente)
    r = cliente.post("/torre/vincular", json={"token_torre": codigo}, headers=h)
    assert r.status_code == 200 and r.json()["torre_id"] == torre


def test_vincular_sem_codigo_e_422(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    h, _ = login(cliente)
    assert cliente.post("/torre/vincular", json={"apelido": "x"}, headers=h).status_code == 422


def test_desvincular_torre_inexistente_ou_de_outro(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    torre, codigo = nova_torre(cliente)
    dono, _ = login(cliente)
    outro, _ = login(cliente)
    cliente.post("/torre/vincular", json={"codigo": codigo}, headers=dono)
    assert cliente.delete("/torre/AT-NAOEXISTE01/vinculo", headers=dono).status_code == 404
    assert cliente.delete(f"/torre/{torre}/vinculo", headers=outro).status_code == 404


def test_admin_lista_troca_codigo_e_reenvia(cliente_e_eventos):
    cliente, eventos = cliente_e_eventos
    torre, codigo = nova_torre(cliente)
    h, _ = login(cliente)
    cliente.post("/torre/vincular", json={"codigo": codigo}, headers=h)

    assert torre in [t["id"] for t in cliente.get("/admin/torres", headers=ADMIN).json()]

    novo = cliente.post(f"/admin/torres/{torre.lower()}/novo-codigo", headers=ADMIN)
    assert novo.status_code == 200 and novo.json()["codigoAtivacao"] != codigo
    assert eventos[-1][0] == "torre.desvinculada" and eventos[-1][1]["donoId"] is None
    assert cliente.get("/auth/me", headers=h).json()["torres"] == []
    assert cliente.post("/torre/vincular", json={"codigo": codigo}, headers=h).status_code == 400

    r = cliente.post("/admin/sincronizar", headers=ADMIN)
    assert r.status_code == 200 and r.json()["reenviadas"] >= 1
    assert eventos[-1][0] == "torre.sincronizada"


def test_admin_novo_codigo_de_torre_inexistente(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    assert cliente.post("/admin/torres/AT-NAOEXISTE01/novo-codigo", headers=ADMIN).status_code == 404


def test_cadastro_repetido_e_409(cliente_e_eventos):
    cliente, _ = cliente_e_eventos
    torre, _ = nova_torre(cliente)
    r = cliente.post("/admin/torres", json={"torreId": torre, "kit": "pro"}, headers=ADMIN)
    assert r.status_code == 409


def test_sincronizar_com_rabbitmq_fora_e_503(cliente_e_eventos, monkeypatch):
    cliente, _ = cliente_e_eventos
    nova_torre(cliente)

    def falha(tipo, torre):
        raise modulo_eventos.FalhaAoPublicar("unroutable")
    monkeypatch.setattr(modulo_eventos, "publicar", falha)
    r = cliente.post("/admin/sincronizar", headers=ADMIN)
    assert r.status_code == 503 and "unroutable" in r.json()["detail"]


def test_google_invalido_da_401(cliente_e_eventos, monkeypatch):
    import google_auth
    cliente, _ = cliente_e_eventos

    def recusa(token, ids):
        raise google_auth.TokenGoogleInvalido("expirado")
    monkeypatch.setattr(google_auth, "verificar", recusa)
    assert cliente.post("/auth/google", json={"token": "x"}).status_code == 401


def test_login_de_novo_atualiza_nome_e_email(cliente_e_eventos, monkeypatch):
    import google_auth
    cliente, _ = cliente_e_eventos
    conta = google_auth.ContaGoogle(sub="google-77", email="velho@x.com", nome="Antigo")
    monkeypatch.setattr(google_auth, "verificar", lambda token, ids: conta)
    cliente.post("/auth/google", json={"token": "x"})
    conta.email, conta.nome = "novo@x.com", "Novo"
    r = cliente.post("/auth/google", json={"token": "x"}).json()
    assert r["usuario"] == {"id": "google-77", "email": "novo@x.com", "nome": "Novo"}


def test_usuario_apagado_do_banco_precisa_entrar_de_novo(cliente_e_eventos):
    import sessao
    cliente, _ = cliente_e_eventos
    token = sessao.emitir("dev:fantasma")
    r = cliente.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401 and "Entre de novo" in r.json()["detail"]


def test_dois_usuarios_no_mesmo_instante_so_um_vincula(cliente_e_eventos, monkeypatch):
    """Corrida: outra requisicao vinculou entre a checagem e o UPDATE."""
    from banco import SessionLocal, Torre
    cliente, _ = cliente_e_eventos
    torre, codigo = nova_torre(cliente)
    h, _ = login(cliente)
    original = regras_torre.torres_do_usuario

    def outro_chega_antes(db, usuario_id):
        with SessionLocal() as s:
            s.get(Torre, torre).dono_id = "dev:mais-rapido"
            s.commit()
        return original(db, usuario_id)

    monkeypatch.setattr(regras_torre, "torres_do_usuario", outro_chega_antes)
    assert cliente.post("/torre/vincular", json={"codigo": codigo}, headers=h).status_code == 409
