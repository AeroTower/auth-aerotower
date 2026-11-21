"""Servico A — API de identidade e vinculo das torres AeroTower.

Responsabilidades:
* login com Google -> token de sessao do AeroTower (aceito tambem pelo Backend);
* vinculo pessoa <-> torre pelo codigo do adesivo, com as regras de negocio;
* cadastro de fabrica das torres;
* publicacao de eventos no RabbitMQ para o Servico B (worker) propagar.

Este arquivo so monta a aplicacao. Cada parte mora no seu modulo:

    schemas.py        formato dos pedidos
    dependencias.py   quem esta logado, chave de admin
    regras_torre.py   regras de negocio (vinculo, fabrica)
    contas.py         conta do usuario e resposta do login
    erros.py          erros das regras -> status HTTP
    rotas/            rotas HTTP, uma por assunto

O que mudou em relacao a versao anterior esta no README (secao "Correcoes").
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from banco import Base, engine
from config import CORS_ORIGENS
from erros import registrar_handler
from rotas import admin, login, saude, torres

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AeroTower — Serviço de Autenticação")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGENS,
    allow_credentials=False,   # o token vai no header, nao em cookie
    allow_methods=["*"],
    allow_headers=["*"],
)
registrar_handler(app)

app.include_router(saude.router)
app.include_router(login.router)
app.include_router(torres.router)
app.include_router(admin.router)
