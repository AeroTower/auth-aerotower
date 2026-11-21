"""Testes unitarios da publicacao de eventos (RabbitMQ trocado por duble)."""
import json

import pytest

import eventos


class CanalFalso:
    def __init__(self, recusa=False):
        self.publicados, self.confirmado, self._recusa = [], False, recusa

    def exchange_declare(self, **kw):
        self.exchange = kw

    def confirm_delivery(self):
        self.confirmado = True

    def basic_publish(self, **kw):
        if self._recusa:
            raise eventos.pika.exceptions.UnroutableError([])
        self.publicados.append(kw)


class ConexaoFalsa:
    def __init__(self, canal):
        self._canal = canal

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def channel(self):
        return self._canal


def _broker(monkeypatch, canal):
    monkeypatch.setattr(eventos.pika, "BlockingConnection", lambda parametros: ConexaoFalsa(canal))


def test_publica_estado_completo_com_confirmacao(monkeypatch):
    canal = CanalFalso()
    _broker(monkeypatch, canal)
    eventos.publicar("torre.vinculada", {"id": "AT-AAAA0001", "versao": 2})

    enviado = canal.publicados[0]
    assert canal.confirmado and enviado["mandatory"] is True
    assert enviado["routing_key"] == "torre.vinculada"
    assert enviado["properties"].delivery_mode == 2          # mensagem persistente
    corpo = json.loads(enviado["body"])
    assert corpo["tipo"] == "torre.vinculada" and corpo["torre"]["versao"] == 2
    assert canal.exchange["exchange_type"] == "topic" and canal.exchange["durable"] is True


def test_sem_fila_ligada_a_publicacao_falha(monkeypatch):
    _broker(monkeypatch, CanalFalso(recusa=True))
    with pytest.raises(eventos.FalhaAoPublicar):
        eventos.publicar("torre.cadastrada", {"id": "AT-AAAA0001"})


def test_broker_fora_do_ar(monkeypatch):
    def recusa(parametros):
        raise eventos.pika.exceptions.AMQPConnectionError("recusado")
    monkeypatch.setattr(eventos.pika, "BlockingConnection", recusa)
    with pytest.raises(eventos.FalhaAoPublicar, match="recusado"):
        eventos.publicar("torre.cadastrada", {"id": "AT-AAAA0001"})
