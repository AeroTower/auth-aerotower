import pika
import json
import time
import os

def processar_vinculo(ch, method, properties, body):
    dados = json.loads(body)
    user_email = dados.get('user_email')
    tower_id = dados.get('tower_id')
    
    print(f"\n[Worker] A processar evento: Vinculando a Torre [{tower_id}] ao utilizador [{user_email}]...")
    
    # Simula o trabalho pesado em background (ex: gravação restrita na base de dados, configuração de chaves MQTT)
    time.sleep(3)
    
    print(f"[Worker] Sucesso! A Torre [{tower_id}] agora pertence exclusivamente a [{user_email}].")
    
    # Confirmação (ACK) para o RabbitMQ remover a mensagem da fila com segurança
    ch.basic_ack(delivery_tag=method.delivery_tag)

def iniciar_consumidor():
    host = os.getenv("RABBITMQ_HOST", "localhost")
    
    print(f"[Worker] A tentar ligar ao RabbitMQ em '{host}'...")
    conexao = pika.BlockingConnection(pika.ConnectionParameters(host=host))
    canal = conexao.channel()
    
    # Garante que a fila existe
    canal.queue_declare(queue='fila_vinculo_torre', durable=True)
    
    # Garante que o worker só pega uma mensagem por vez para processar de forma justa
    canal.basic_qos(prefetch_count=1)
    canal.basic_consume(queue='fila_vinculo_torre', on_message_callback=processar_vinculo)
    
    print("[Worker] A escutar eventos de vínculo de torres. Pressione CTRL+C para sair.")
    canal.start_consuming()

if __name__ == "__main__":
    # Pequena pausa para dar tempo ao RabbitMQ subir totalmente no docker-compose
    time.sleep(5)
    iniciar_consumidor()