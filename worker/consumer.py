import pika
import json
import time
import os

# "Base de dados" em memória para controlar os vínculos ativos
# Formato: { "tower_id": "user_email" } -> Guarda qual utilizador é dono de qual torre
torres_ocupadas = {}
# Formato: { "user_email": "tower_id" } -> Guarda qual torre pertence a cada utilizador
utilizadores_com_torre = {}

def processar_vinculo(ch, method, properties, body):
    dados = json.loads(body)
    user_email = dados.get('user_email')
    tower_id = dados.get('tower_id')
    
    print(f"\n[Worker] A processar evento: Vinculando a Torre [{tower_id}] ao utilizador [{user_email}]...")
    
    # Validação 1: O mesmo e-mail já está a tentar vincular-se à mesma torre
    if torres_ocupadas.get(tower_id) == user_email:
        print(f"[Worker AVISO] O utilizador [{user_email}] já possui a Torre [{tower_id}] vinculada. Ignorando duplicado.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # Validação 2: Outro e-mail está a tentar vincular-se a uma torre que já pertence a outra pessoa
    if tower_id in torres_ocupadas:
        dono_atual = torres_ocupadas[tower_id]
        print(f"[Worker ERRO] A Torre [{tower_id}] já pertence ao utilizador [{dono_atual}]. Vínculo rejeitado para [{user_email}].")
        ch.basic_ack(delivery_tag=method.delivery_tag) # Faz o ACK para retirar da fila (mensagem inválida por regra de negócio)
        return

    # Validação 3: O mesmo e-mail já tem outra torre vinculada (se a regra for 1 torre por utilizador)
    if user_email in utilizadores_com_torre:
        outra_torre = utilizadores_com_torre[user_email]
        print(f"[Worker ERRO] O utilizador [{user_email}] já possui a Torre [{outra_torre}] vinculada. Não pode ter torres diferentes.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # Se passou por todas as validações, efetiva o vínculo!
    torres_ocupadas[tower_id] = user_email
    utilizadores_com_torre[user_email] = tower_id
    
    time.sleep(1)
    print(f"[Worker Sucesso] A Torre [{tower_id}] foi vinculada com sucesso ao utilizador [{user_email}].")
    
    ch.basic_ack(delivery_tag=method.delivery_tag)

def iniciar_consumidor():
    host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    
    while True:
        try:
            print(f"[Worker] A ligar ao RabbitMQ em '{host}'...")
            conexao = pika.BlockingConnection(pika.ConnectionParameters(host=host))
            canal = conexao.channel()
            
            canal.queue_declare(queue='fila_vinculo_torre', durable=True)
            canal.basic_qos(prefetch_count=1)
            canal.basic_consume(queue='fila_vinculo_torre', on_message_callback=processar_vinculo)
            
            print("[Worker] Ligado com sucesso! À escuta de mensagens na fila...")
            canal.start_consuming()
            break
        except Exception as e:
            print(f"[Worker Erro] Falha na conexão: {e}. A tentar novamente em 3 segundos...")
            time.sleep(3)

if __name__ == "__main__":
    iniciar_consumidor()