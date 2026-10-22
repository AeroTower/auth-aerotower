"""Entrega os eventos de torre ao resto do sistema.

Dois modos (EVENTOS_MODO, ver config.py):
* direto: chama o Backend por HTTP na hora. Sem fila: se o Backend nao
  responder, o vinculo e desfeito e o app recebe 503.
* rabbitmq: publica na exchange topic `aerotower.eventos`; o worker entrega.

Trocar de broker (ex.: Azure Service Bus) = acrescentar um modo aqui e um
consumidor no worker. O resto da API nao muda.

Cada evento leva o ESTADO COMPLETO da torre, nao so "o que mudou". Assim o
consumidor pode reprocessar a mesma mensagem sem estragar nada
(idempotente) e, se perder alguma, a proxima corrige.

Routing keys: torre.cadastrada, torre.vinculada, torre.desvinculada,
torre.sincronizada (reenvio manual pelo admin).
"""
import json
import logging
from datetime import datetime, timezone

import pika
import requests

from config import BACKEND_URL, EVENTOS_MODO, EXCHANGE, RABBITMQ_URL, SERVICO_API_KEY

logger = logging.getLogger(__name__)


class FalhaAoPublicar(Exception):
    pass


def publicar(tipo: str, torre: dict) -> None:
    if EVENTOS_MODO == "rabbitmq":
        _publicar_rabbitmq(tipo, torre)
    else:
        _entregar_direto(tipo, torre)


def _entregar_direto(tipo: str, torre: dict) -> None:
    """Mesmo PUT que o worker faria, so que sincrono."""
    try:
        resposta = requests.put(
            f"{BACKEND_URL}/internal/torres/{torre['id']}",
            json={k: torre.get(k) for k in ("kit", "donoId", "apelido", "versao")},
            headers={"X-Service-Key": SERVICO_API_KEY},
            timeout=60,   # App Service frio demora para acordar
        )
    except requests.RequestException as erro:
        logger.error("Backend indisponível para %s: %s", tipo, erro)
        raise FalhaAoPublicar(str(erro))
    if resposta.status_code >= 400:
        logger.error("Backend recusou %s (%s): %s", tipo, resposta.status_code, resposta.text[:200])
        raise FalhaAoPublicar(f"Backend respondeu {resposta.status_code}")
    logger.info("Evento %s entregue direto ao Backend: %s", tipo, torre)


def _publicar_rabbitmq(tipo: str, torre: dict) -> None:
    corpo = json.dumps({
        "tipo": tipo,
        "torre": torre,
        "emitidoEm": datetime.now(timezone.utc).isoformat(),
    })
    try:
        parametros = pika.URLParameters(RABBITMQ_URL)
        parametros.socket_timeout = 5
        parametros.blocked_connection_timeout = 5
        with pika.BlockingConnection(parametros) as conexao:
            canal = conexao.channel()
            canal.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
            canal.confirm_delivery()   # so volta quando o broker confirmou
            canal.basic_publish(
                exchange=EXCHANGE, routing_key=tipo, body=corpo,
                properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
                mandatory=False,
            )
    except Exception as erro:
        # Antes o erro era so impresso e a API respondia "sucesso" mesmo
        # com o evento perdido. Agora quem chama desfaz a operacao.
        logger.error("Falha ao publicar %s: %s", tipo, erro)
        raise FalhaAoPublicar(str(erro))
    logger.info("Evento %s publicado: %s", tipo, torre)
