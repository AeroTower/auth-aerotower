"""Testes de desempenho do servico de auth.

Limites folgados (cerca de 10x o medido no GitHub Actions): falham so se
algo ficar muito mais lento.
"""
import time

import codigo
import sessao
from apoio import login, nova_torre


def test_carga_de_tokens_de_sessao():
    """Carga: cada requisicao do app valida um token. 5.000 emitidos e validados."""
    inicio = time.perf_counter()
    for i in range(5_000):
        assert sessao.validar(sessao.emitir(f"u{i}")) == f"u{i}"
    assert time.perf_counter() - inicio < 10


def test_volume_de_codigos_de_adesivo_sem_repeticao():
    """Volume: 20.000 adesivos gerados, nenhum repetido."""
    codigos = {codigo.gerar() for _ in range(20_000)}
    assert len(codigos) == 20_000


def test_pico_de_ativacoes_no_dia_de_entrega(cliente_e_eventos):
    """Spike: 100 clientes vinculando a torre ao mesmo tempo do lote entregue."""
    cliente, eventos = cliente_e_eventos
    lote = [nova_torre(cliente) for _ in range(100)]
    pessoas = [login(cliente)[0] for _ in range(100)]

    inicio = time.perf_counter()
    respostas = [cliente.post("/torre/vincular", json={"codigo": c}, headers=h)
                 for (_, c), h in zip(lote, pessoas, strict=True)]
    duracao = time.perf_counter() - inicio

    assert {r.status_code for r in respostas} == {200}
    assert duracao < 15, f"100 vínculos levaram {duracao:.2f}s"


def test_listagem_admin_com_muitas_torres(cliente_e_eventos):
    """Escalabilidade da fabrica: listagem com centenas de torres cadastradas."""
    from apoio import ADMIN
    cliente, _ = cliente_e_eventos
    for _ in range(200):
        nova_torre(cliente, "basico")
    inicio = time.perf_counter()
    r = cliente.get("/admin/torres", headers=ADMIN)
    assert r.status_code == 200 and len(r.json()) >= 200
    assert time.perf_counter() - inicio < 3
