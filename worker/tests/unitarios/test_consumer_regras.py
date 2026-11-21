"""Mais testes unitarios do worker: eventos malformados e preparo da fila."""
import json
from types import SimpleNamespace

import consumer


class Canal:
    def __init__(self):
        self.acks, self.nacks, self.chamadas = [], [], []

    def basic_ack(self, delivery_tag):
        self.acks.append(delivery_tag)

    def basic_nack(self, delivery_tag, requeue):
        self.nacks.append((delivery_tag, requeue))

    def __getattr__(self, nome):
        return lambda **kw: self.chamadas.append((nome, kw))


def _processar(corpo):
    canal = Canal()
    consumer.processar(canal, SimpleNamespace(delivery_tag=1, routing_key="torre.x"), None, corpo)
    return canal


def test_json_quebrado_vai_para_a_fila_de_falhas():
    assert _processar(b"{nao e json").nacks == [(1, False)]
    assert consumer._saude["ultimo_erro"].startswith("descartado")


def test_evento_sem_id_da_torre_vai_para_a_fila_de_falhas(monkeypatch):
    monkeypatch.setattr(consumer.requests, "put", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    assert _processar(json.dumps({"tipo": "torre.vinculada", "torre": {}})).nacks == [(1, False)]


def test_backend_com_erro_500_tenta_de_novo(monkeypatch):
    monkeypatch.setattr(consumer, "ESPERA_S", 0)
    monkeypatch.setattr(consumer.requests, "put", lambda *a, **k: SimpleNamespace(status_code=502, text="bad"))
    corpo = json.dumps({"tipo": "torre.cadastrada", "torre": {"id": "AT-AAAA0001", "versao": 1}})
    assert _processar(corpo).nacks == [(1, True)]


def test_sucesso_conta_na_pagina_de_saude(monkeypatch):
    monkeypatch.setattr(consumer.requests, "put", lambda *a, **k: SimpleNamespace(status_code=200, text=""))
    antes = consumer._saude["processados"]
    _processar(json.dumps({"tipo": "torre.cadastrada", "torre": {"id": "AT-AAAA0001", "versao": 1}}))
    assert consumer._saude["processados"] == antes + 1 and consumer._saude["ultimo_sucesso"]


def test_preparar_cria_fila_com_dead_letter_e_uma_mensagem_por_vez():
    canal = Canal()
    consumer.preparar(canal)
    nomes = [c[0] for c in canal.chamadas]
    assert nomes == ["exchange_declare", "queue_declare", "queue_declare", "queue_bind", "basic_qos"]
    fila = canal.chamadas[2][1]
    assert fila["queue"] == "backend.torres"
    assert fila["arguments"]["x-dead-letter-routing-key"] == "backend.torres.falhas"
    assert canal.chamadas[3][1]["routing_key"] == "torre.*"
    assert canal.chamadas[4][1] == {"prefetch_count": 1}
