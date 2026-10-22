"""Servico B — worker de onboarding das torres.

Consome os eventos `torre.*` publicados pelo Servico A e leva o estado de
cada torre para o Backend (quem recebe a telemetria e manda na bomba), via
PUT /internal/torres/{id}.

Garantias:
* ack manual: a mensagem so sai da fila depois que o Backend confirmou;
* Backend fora do ar (rede, 5xx): espera e devolve a mensagem para a fila;
* evento com dado ruim (4xx): vai para a fila de falhas
  `backend.torres.falhas`, para alguem olhar, em vez de travar a fila;
* eventos levam o estado completo + versao, entao reprocessar e seguro.

Proximo passo natural aqui: criar a credencial MQTT da torre no HiveMQ
quando chegar `torre.cadastrada` (plano Starter, API de credenciais).
"""
import json
import logging
import os
import time

import pika
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s worker: %(message)s")
log = logging.getLogger("worker")

RABBITMQ_URL = os.getenv("RABBITMQ_URL") or f"amqp://guest:guest@{os.getenv('RABBITMQ_HOST', 'localhost')}:5672/%2F"
EXCHANGE     = os.getenv("RABBITMQ_EXCHANGE", "aerotower.eventos")
FILA         = "backend.torres"
FILA_FALHAS  = "backend.torres.falhas"
BACKEND_URL  = os.getenv("BACKEND_URL", "http://localhost:8001").rstrip("/")
SERVICO_KEY  = os.getenv("SERVICO_API_KEY", "")
ESPERA_S     = float(os.getenv("WORKER_ESPERA_S", "5"))


class ErroTemporario(Exception):
    """Vale tentar de novo (Backend dormindo, rede)."""


class ErroPermanente(Exception):
    """Tentar de novo nao adianta (evento malformado, chave errada)."""


def aplicar_no_backend(evento: dict) -> None:
    torre = evento.get("torre") or {}
    torre_id = torre.get("id")
    if not torre_id:
        raise ErroPermanente("evento sem torre.id")
    try:
        resposta = requests.put(
            f"{BACKEND_URL}/internal/torres/{torre_id}",
            json={k: torre.get(k) for k in ("kit", "donoId", "apelido", "versao")},
            headers={"X-Service-Key": SERVICO_KEY},
            timeout=60,   # App Service frio demora para acordar
        )
    except requests.RequestException as erro:
        raise ErroTemporario(str(erro))
    if resposta.status_code >= 500 or resposta.status_code == 429:
        raise ErroTemporario(f"Backend respondeu {resposta.status_code}")
    if resposta.status_code >= 400:
        raise ErroPermanente(f"Backend respondeu {resposta.status_code}: {resposta.text[:200]}")


def processar(canal, metodo, propriedades, corpo):
    try:
        evento = json.loads(corpo)
        log.info("Recebido %s: %s", metodo.routing_key, evento.get("torre"))
        aplicar_no_backend(evento)
        canal.basic_ack(delivery_tag=metodo.delivery_tag)
        log.info("Backend atualizado (%s)", evento["torre"]["id"])
    except ErroTemporario as erro:
        log.warning("Backend indisponível (%s). Nova tentativa em %ss.", erro, ESPERA_S)
        time.sleep(ESPERA_S)
        canal.basic_nack(delivery_tag=metodo.delivery_tag, requeue=True)
    except (ErroPermanente, ValueError, KeyError) as erro:
        log.error("Evento descartado para %s: %s", FILA_FALHAS, erro)
        canal.basic_nack(delivery_tag=metodo.delivery_tag, requeue=False)  # dead-letter


def preparar(canal) -> None:
    canal.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    canal.queue_declare(queue=FILA_FALHAS, durable=True)
    canal.queue_declare(queue=FILA, durable=True, arguments={
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": FILA_FALHAS,
    })
    canal.queue_bind(queue=FILA, exchange=EXCHANGE, routing_key="torre.*")
    canal.basic_qos(prefetch_count=1)   # uma por vez: mantem a ordem dos eventos


def iniciar_worker():
    if not SERVICO_KEY:
        log.warning("SERVICO_API_KEY vazia: o Backend vai recusar as atualizações.")
    while True:
        try:
            log.info("Conectando ao RabbitMQ...")
            conexao = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            canal = conexao.channel()
            preparar(canal)
            canal.basic_consume(queue=FILA, on_message_callback=processar)
            log.info("Aguardando eventos em '%s' -> %s", FILA, BACKEND_URL)
            canal.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            log.warning("RabbitMQ indisponível. Nova tentativa em 5 s.")
            time.sleep(5)


if __name__ == "__main__":
    iniciar_worker()
