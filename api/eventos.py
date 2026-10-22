"""Publica eventos no RabbitMQ (exchange topic `aerotower.eventos`).

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

from config import EXCHANGE, RABBITMQ_URL

logger = logging.getLogger(__name__)


class FalhaAoPublicar(Exception):
    pass


def publicar(tipo: str, torre: dict) -> None:
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
