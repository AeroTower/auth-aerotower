import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import consumer  # noqa: E402


class Canal:
    def __init__(self):
        self.acks, self.nacks = [], []

    def basic_ack(self, delivery_tag):
        self.acks.append(delivery_tag)

    def basic_nack(self, delivery_tag, requeue):
        self.nacks.append((delivery_tag, requeue))


def _evento():
    return json.dumps({"tipo": "torre.vinculada",
                       "torre": {"id": "AT-1A2B3C", "kit": "pro", "donoId": "u1", "apelido": None, "versao": 2}})


def _rodar(monkeypatch, comportamento):
    monkeypatch.setattr(consumer, "ESPERA_S", 0)
    monkeypatch.setattr(consumer.requests, "put", comportamento)
    canal = Canal()
    consumer.processar(canal, SimpleNamespace(delivery_tag=7, routing_key="torre.vinculada"), None, _evento())
    return canal


def test_sucesso_confirma(monkeypatch):
    canal = _rodar(monkeypatch, lambda *a, **k: SimpleNamespace(status_code=200, text=""))
    assert canal.acks == [7]


def test_backend_fora_devolve_para_a_fila(monkeypatch):
    def cai(*a, **k):
        raise consumer.requests.ConnectionError("recusado")
    canal = _rodar(monkeypatch, cai)
    assert canal.nacks == [(7, True)]


def test_evento_recusado_vai_para_falhas(monkeypatch):
    canal = _rodar(monkeypatch, lambda *a, **k: SimpleNamespace(status_code=422, text="kit"))
    assert canal.nacks == [(7, False)]


def test_backend_parado_ou_chave_errada_espera(monkeypatch):
    """403 da Azure (app parado), 401 e 404: tenta de novo, não descarta."""
    for status in (401, 403, 404):
        canal = _rodar(monkeypatch, lambda *a, s=status, **k: SimpleNamespace(
            status_code=s, text="Error 403 - This web app is stopped."))
        assert canal.nacks == [(7, True)], status


def test_so_o_reenvio_do_admin_forca(monkeypatch):
    enviados = []

    def put(url, json, **k):
        enviados.append(json)
        return SimpleNamespace(status_code=200, text="")

    monkeypatch.setattr(consumer.requests, "put", put)
    torre = {"id": "AT-SIMULADA01", "kit": "pro", "donoId": None, "apelido": None, "versao": 3}
    consumer.aplicar_no_backend({"tipo": "torre.desvinculada", "torre": torre})
    consumer.aplicar_no_backend({"tipo": "torre.sincronizada", "torre": torre})
    assert [e["forcar"] for e in enviados] == [False, True]
