import os
import json
import time
import pika

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")

# Simulação do banco de dados relacional no Worker
# Formato: { "email_usuario": "token_da_torre" }
db_torres = {}

def processar_mensagem(ch, method, properties, body):
    try:
        dados = json.loads(body)
        email = dados.get("email")
        token_torre = dados.get("token_torre")

        print(f"\n=== [WORKER] Nova mensagem recebida da fila 'vincular_torre' ===", flush=True)
        print(f"=== [WORKER] Processando: Usuário '{email}' -> Torre '{token_torre}' ===", flush=True)

        # ----------------------------------------------------------------------
        # REGRA DE NEGÓCIO 1: O utilizador já possui uma torre vinculada?
        # ----------------------------------------------------------------------
        if email in db_torres:
            torre_atual = db_torres[email]
            print(f"=== [REJEITADO] O e-mail '{email}' já possui a torre '{torre_atual}' cadastrada. ===", flush=True)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # ----------------------------------------------------------------------
        # REGRA DE NEGÓCIO 2: A torre já está atribuída a outro utilizador?
        # ----------------------------------------------------------------------
        if token_torre in db_torres.values():
            print(f"=== [REJEITADO] A AeroTower '{token_torre}' já pertence a outro utilizador. ===", flush=True)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # ----------------------------------------------------------------------
        # PERSISTÊNCIA E EXECUÇÃO
        # ----------------------------------------------------------------------
        db_torres[email] = token_torre
        print(f"=== [SUCESSO] Vínculo ativado com êxito! {email} <-> {token_torre} ===", flush=True)
        print(f"=== [BANCO ATUAL] {db_torres} ===", flush=True)

        # Confirma ao RabbitMQ que a mensagem foi processada com sucesso
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"=== [ERRO CRÍTICO WORKER] Falha ao processar mensagem: {e} ===", flush=True)
        # Em caso de erro inesperado de sintaxe/dados, remove a mensagem para não travar a fila
        ch.basic_ack(delivery_tag=method.delivery_tag)

def iniciar_worker():
    """Tenta conectar ao RabbitMQ com suporte a retry caso o broker esteja inicializando."""
    while True:
        try:
            print("=== [WORKER] Conectando ao RabbitMQ... ===", flush=True)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )
            channel = connection.channel()

            # Garante que a fila existe
            channel.queue_declare(queue='vincular_torre', durable=True)

            # Distribui 1 mensagem por vez para o worker
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue='vincular_torre', on_message_callback=processar_mensagem)

            print("=== [WORKER] Conectado e aguardando eventos na fila 'vincular_torre'... ===", flush=True)
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError:
            print("=== [WORKER] RabbitMQ ainda indisponível. Aguardando 5 segundos... ===", flush=True)
            time.sleep(5)

if __name__ == '__main__':
    iniciar_worker()