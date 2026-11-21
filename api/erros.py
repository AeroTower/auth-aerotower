"""Erros das regras de negocio e como cada um vira resposta HTTP.

As regras (regras_torre.py, contas.py) nao conhecem HTTP: elas levantam
estes erros, e o handler registrado no main.py os traduz. Assim a regra
pode ser testada e reaproveitada sem o FastAPI.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ErroDeRegra(Exception):
    """Base: `status` e o codigo HTTP; a mensagem vai para o app em `detail`."""

    status = 400

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


class CodigoInvalido(ErroDeRegra):
    status = 400

    def __init__(self):
        super().__init__("Código de ativação inválido.")


class LimiteDeTorres(ErroDeRegra):
    status = 400


class TorreDeOutroDono(ErroDeRegra):
    status = 409

    def __init__(self):
        super().__init__("Esta AeroTower já está associada a outro usuário.")


class TorreNaoEncontrada(ErroDeRegra):
    status = 404

    def __init__(self):
        super().__init__("Torre não encontrada.")


class DadoInvalido(ErroDeRegra):
    status = 422


class TorreJaCadastrada(ErroDeRegra):
    status = 409


class EventoNaoEntregue(ErroDeRegra):
    """O RabbitMQ nao recebeu o evento: nada foi gravado."""

    status = 503


class LoginRecusado(ErroDeRegra):
    status = 401


class RotaDesligada(ErroDeRegra):
    """Em producao a rota de teste responde como se nao existisse."""

    status = 404

    def __init__(self):
        super().__init__("Não encontrado.")


def registrar_handler(app: FastAPI) -> None:
    @app.exception_handler(ErroDeRegra)
    async def _responder(request: Request, erro: ErroDeRegra) -> JSONResponse:
        return JSONResponse(status_code=erro.status, content={"detail": erro.mensagem})
