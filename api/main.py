from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import pika
import json
import os

app = FastAPI()

# Modelo de dados para receber via JSON no corpo da requisição (Body)
class TorreVinculo(BaseModel):
    user_email: str
    tower_id: str

def publicar_na_fila(dados):
    host = os.getenv("RABBITMQ_HOST", "localhost")
    conexao = pika.BlockingConnection(pika.ConnectionParameters(host=host))
    canal = conexao.channel()
    
    # Declara a fila durável
    canal.queue_declare(queue='fila_vinculo_torre', durable=True)
    
    canal.basic_publish(
        exchange='',
        routing_key='fila_vinculo_torre',
        body=json.dumps(dados),
        properties=pika.BasicProperties(delivery_mode=2) # Torna a mensagem persistente
    )
    conexao.close()
    print(f"[API] Mensagem publicada na fila com sucesso: {dados}")

@app.post("/torre/vincular")
def vincular_torre(vinculo: TorreVinculo):
    # Converte os dados do corpo para dicionário
    evento = {
        "user_email": vinculo.user_email,
        "tower_id": vinculo.tower_id
    }
    
    try:
        publicar_na_fila(evento)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao publicar no RabbitMQ: {str(e)}"
        )
    
    return {
        "status": "processando", 
        "mensagem": f"Solicitação de vínculo da torre {vinculo.tower_id} para {vinculo.user_email} enviada com sucesso!"
    }