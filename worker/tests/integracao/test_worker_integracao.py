"""Testes de integracao do worker: pagina de saude por HTTP e laco de conexao."""
import json
import socket
import time
import urllib.error
import urllib.request

import pytest

import consumer


def _porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read())


def test_sem_porta_nao_sobe_servidor(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("WEBSITES_PORT", raising=False)
    assert consumer.iniciar_saude() is None


def test_pagina_de_saude_responde_503_ate_conectar(monkeypatch):
    porta = _porta_livre()
    monkeypatch.setenv("PORT", str(porta))
    monkeypatch.setattr(consumer, "SERVICO_KEY", "chave-secreta-do-servico")
    consumer.iniciar_saude()
    time.sleep(0.2)

    monkeypatch.setitem(consumer._saude, "conectado", False)
    status, corpo = _get(f"http://127.0.0.1:{porta}/")
    assert status == 503 and corpo["servico"] == "auth-aerotower-worker"

    monkeypatch.setitem(consumer._saude, "conectado", True)
    status, corpo = _get(f"http://127.0.0.1:{porta}/")
    assert status == 200 and corpo["conectado"] is True
    assert "chave-secreta-do-servico" not in json.dumps(corpo)   # a chave nunca aparece


class _Para(Exception):
    """Interrompe o laco infinito do worker no teste."""


def test_worker_tenta_de_novo_ate_o_rabbitmq_aparecer(monkeypatch):
    tentativas, esperas, consumindo = [], [], []

    class Canal:
        def __getattr__(self, nome):
            return lambda *a, **k: None

        def basic_consume(self, queue, on_message_callback):
            assert queue == "backend.torres" and on_message_callback is consumer.processar

        def start_consuming(self):
            consumindo.append(consumer._saude["conectado"])
            raise _Para

    class Conexao:
        def channel(self):
            return Canal()

    def conectar(parametros):
        tentativas.append(1)
        if len(tentativas) == 1:
            raise consumer.pika.exceptions.AMQPConnectionError("ainda subindo")
        return Conexao()

    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr(consumer, "SERVICO_KEY", "")
    monkeypatch.setattr(consumer.pika, "BlockingConnection", conectar)
    monkeypatch.setattr(consumer.time, "sleep", esperas.append)
    with pytest.raises(_Para):
        consumer.iniciar_worker()
    assert len(tentativas) == 2 and esperas == [5] and consumindo == [True]
