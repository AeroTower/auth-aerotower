"""Servico A — API de identidade e vinculo das torres AeroTower.

Responsabilidades:
* login com Google -> token de sessao do AeroTower (aceito tambem pelo Backend);
* vinculo pessoa <-> torre pelo codigo do adesivo, com as regras de negocio;
* cadastro de fabrica das torres;
* publicacao de eventos no RabbitMQ para o Servico B (worker) propagar.

O que mudou em relacao a versao anterior esta no README (secao "Correcoes").
"""
import logging
import secrets
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

import codigo as codigos
import eventos
import google_auth
import sessao
from banco import Base, Torre, Usuario, engine, get_db
from config import (
    ADMIN_API_KEY,
    AUTH_MODO_DEV,
    CORS_ORIGENS,
    GOOGLE_CLIENT_IDS,
    MAX_TORRES_POR_USUARIO,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("auth")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AeroTower — Serviço de Autenticação")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGENS,
    allow_credentials=False,   # o token vai no header, nao em cookie
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================
# Schemas
# =============================================
class TokenSchema(BaseModel):
    token: str = Field(..., description="ID token (celular) ou access token (web) do Google")


class LoginDevSchema(BaseModel):
    id: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._@+-]+$")


class VincularTorreSchema(BaseModel):
    codigo: Optional[str] = Field(None, description="Código do adesivo, ex.: K9X2-7QHM")
    # Nome antigo do campo, aceito para nao quebrar o app durante a transicao.
    token_torre: Optional[str] = None
    apelido: Optional[str] = Field(None, max_length=40)

    @model_validator(mode="after")
    def _algum_codigo(self):
        if not (self.codigo or self.token_torre):
            raise ValueError("Informe o código do adesivo.")
        return self

    @property
    def codigo_informado(self) -> str:
        return self.codigo or self.token_torre


class CadastrarTorreSchema(BaseModel):
    torreId: str
    kit: str


# =============================================
# Dependencias
# =============================================
def usuario_logado(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Usuario:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Faça login para continuar.")
    try:
        usuario_id = sessao.validar(authorization.split(" ", 1)[1].strip())
    except sessao.SessaoInvalida as erro:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(erro))
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário não encontrado. Entre de novo.")
    return usuario


def exigir_admin(x_admin_key: Optional[str] = Header(default=None)) -> None:
    if not ADMIN_API_KEY:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Rotas de admin desligadas (ADMIN_API_KEY vazia).")
    if not x_admin_key or not secrets.compare_digest(x_admin_key, ADMIN_API_KEY):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Chave de admin inválida.")


# =============================================
# Auxiliares
# =============================================
def _torres_do_usuario(db: Session, usuario_id: str) -> List[Torre]:
    return db.query(Torre).filter(Torre.dono_id == usuario_id).order_by(Torre.vinculada_em).all()


def _resposta_login(db: Session, usuario: Usuario) -> dict:
    torres = _torres_do_usuario(db, usuario.id)
    return {
        "status":       "success",
        "token":        sessao.emitir(usuario.id, usuario.email),
        "usuario":      {"id": usuario.id, "email": usuario.email, "nome": usuario.nome},
        # Campos que o app ja usava:
        "email":        usuario.email,
        "possui_torre": bool(torres),
        "torre_id":     torres[0].id if torres else None,
    }


def _salvar_usuario(db: Session, sub: str, email: Optional[str], nome: Optional[str]) -> Usuario:
    usuario = db.get(Usuario, sub)
    if usuario is None:
        usuario = Usuario(id=sub)
        db.add(usuario)
    usuario.email, usuario.nome = email, nome
    db.commit()
    return usuario


def _publicar_ou_desfazer(db: Session, tipo: str, torre: Torre) -> None:
    """Grava so se o evento chegou ao RabbitMQ; senao, desfaz e avisa o app.

    Assim banco e Backend nao ficam discordando em silencio. (Ainda resta a
    janela minuscula de o commit falhar depois da publicacao; o reenvio em
    /admin/sincronizar corrige. O padrao "outbox" resolveria de vez.)
    """
    db.flush()
    estado = torre.estado()
    try:
        eventos.publicar(tipo, estado)
    except eventos.FalhaAoPublicar:
        db.rollback()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Serviço temporariamente indisponível. Tente de novo em instantes.")
    db.commit()


def _resposta_vinculo(torre: Torre, mensagem: str) -> dict:
    return {
        "status":   "success",
        "message":  mensagem,
        "torre_id": torre.id,
        "kit":      torre.kit,
        "apelido":  torre.apelido,
    }


# =============================================
# Rotas — saude
# =============================================
@app.get("/")
def home():
    return {
        "servico": "auth-aerotower",
        "status": "online",
        "google_configurado": bool(GOOGLE_CLIENT_IDS),
        "max_torres_por_usuario": MAX_TORRES_POR_USUARIO,
    }


# =============================================
# Rotas — login
# =============================================
@app.post("/auth/google")
def auth_google(data: TokenSchema, db: Session = Depends(get_db)):
    try:
        conta = google_auth.verificar(data.token, GOOGLE_CLIENT_IDS)
    except google_auth.TokenGoogleInvalido as erro:
        logger.info("Login Google recusado: %s", erro)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token do Google inválido")
    usuario = _salvar_usuario(db, conta.sub, conta.email, conta.nome)
    return _resposta_login(db, usuario)


@app.post("/auth/dev", summary="Login sem Google (só com AUTH_MODO_DEV=true)")
def auth_dev(data: LoginDevSchema, db: Session = Depends(get_db)):
    if not AUTH_MODO_DEV:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Não encontrado.")
    identificador = data.id.strip()
    usuario = _salvar_usuario(db, f"dev:{identificador}", f"{identificador}@dev.local", identificador)
    return _resposta_login(db, usuario)


@app.get("/auth/me")
def eu(usuario: Usuario = Depends(usuario_logado), db: Session = Depends(get_db)):
    return {
        "usuario": {"id": usuario.id, "email": usuario.email, "nome": usuario.nome},
        "torres":  [{"id": t.id, "kit": t.kit, "apelido": t.apelido}
                    for t in _torres_do_usuario(db, usuario.id)],
    }


# =============================================
# Rotas — vinculo (regras de negocio)
# =============================================
@app.post("/torre/vincular")
def vincular_torre(
    data: VincularTorreSchema,
    usuario: Usuario = Depends(usuario_logado),
    db: Session = Depends(get_db),
):
    # Quem vincula e quem esta logado. Antes o e-mail vinha no corpo e
    # qualquer pessoa podia vincular uma torre ao e-mail de outra.
    informado = data.codigo_informado
    if not codigos.valido(informado):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Código de ativação inválido.")

    torre = db.query(Torre).filter(Torre.codigo_hash == codigos.hash_de(informado)).first()
    if torre is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Código de ativação inválido.")

    if torre.dono_id == usuario.id:   # repetiu o pedido: tudo certo
        return _resposta_vinculo(torre, "Esta torre já está vinculada a você.")

    # REGRA DE NEGOCIO 1: limite de torres por usuario (hoje 1)
    atuais = _torres_do_usuario(db, usuario.id)
    if len(atuais) >= MAX_TORRES_POR_USUARIO:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Você já possui a torre '{atuais[0].apelido or atuais[0].id}' vinculada.",
        )

    # REGRA DE NEGOCIO 2: a torre ja tem dono?
    if torre.dono_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta AeroTower já está associada a outro usuário.")

    # UPDATE condicional: se duas pessoas usarem o mesmo codigo ao mesmo
    # tempo, so uma encontra dono_id ainda vazio.
    alteradas = (
        db.query(Torre)
        .filter(Torre.id == torre.id, Torre.dono_id.is_(None))
        .update({
            Torre.dono_id: usuario.id,
            Torre.apelido: (data.apelido or "").strip() or None,
            Torre.vinculada_em: datetime.now(),
            Torre.versao: Torre.versao + 1,
        }, synchronize_session=False)
    )
    if alteradas == 0:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta AeroTower já está associada a outro usuário.")
    db.refresh(torre)
    _publicar_ou_desfazer(db, "torre.vinculada", torre)
    logger.info("Torre %s vinculada a %s", torre.id, usuario.id)
    return _resposta_vinculo(torre, "Torre vinculada com sucesso!")


@app.delete("/torre/{torre_id}/vinculo", summary="Desvincula a torre da conta (para passar adiante)")
def desvincular(torre_id: str, usuario: Usuario = Depends(usuario_logado), db: Session = Depends(get_db)):
    torre = db.get(Torre, torre_id.upper())
    if torre is None or torre.dono_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Torre não encontrada.")
    torre.dono_id, torre.apelido, torre.vinculada_em = None, None, None
    torre.versao += 1
    _publicar_ou_desfazer(db, "torre.desvinculada", torre)
    return {"status": "success", "message": "Torre desvinculada. O código do adesivo volta a valer."}


# =============================================
# Rotas — fabrica (admin)
# =============================================
@app.post("/admin/torres", status_code=201, dependencies=[Depends(exigir_admin)])
def cadastrar_torre(data: CadastrarTorreSchema, db: Session = Depends(get_db)):
    torre_id = data.torreId.strip().upper()
    if not codigos.id_torre_valido(torre_id):
        raise HTTPException(422, "Id de torre inválido. Use AT-<MAC>, ex.: AT-24DCC3A1B2C4.")
    if data.kit not in codigos.KITS:
        raise HTTPException(422, f"Kit inválido. Use um de: {', '.join(codigos.KITS)}.")
    if db.get(Torre, torre_id) is not None:
        raise HTTPException(409, f"A torre {torre_id} já está cadastrada.")

    codigo = codigos.gerar()
    torre = Torre(id=torre_id, kit=data.kit, codigo_hash=codigos.hash_de(codigo), versao=1)
    db.add(torre)
    _publicar_ou_desfazer(db, "torre.cadastrada", torre)
    return {"torreId": torre.id, "kit": torre.kit, "codigoAtivacao": codigo}


@app.post("/admin/torres/{torre_id}/novo-codigo", dependencies=[Depends(exigir_admin)])
def novo_codigo(torre_id: str, db: Session = Depends(get_db)):
    """Adesivo perdido ou torre devolvida: desvincula e troca o codigo."""
    torre = db.get(Torre, torre_id.upper())
    if torre is None:
        raise HTTPException(404, "Torre não encontrada.")
    codigo = codigos.gerar()
    torre.codigo_hash = codigos.hash_de(codigo)
    torre.dono_id, torre.apelido, torre.vinculada_em = None, None, None
    torre.versao += 1
    _publicar_ou_desfazer(db, "torre.desvinculada", torre)
    return {"torreId": torre.id, "kit": torre.kit, "codigoAtivacao": codigo}


@app.get("/admin/torres", dependencies=[Depends(exigir_admin)])
def listar_torres(db: Session = Depends(get_db)):
    return [
        {**t.estado(), "vinculadaEm": t.vinculada_em, "criadaEm": t.criada_em}
        for t in db.query(Torre).order_by(Torre.criada_em).all()
    ]


@app.post("/admin/sincronizar", dependencies=[Depends(exigir_admin)])
def sincronizar(db: Session = Depends(get_db)):
    """Reenvia o estado de todas as torres (Backend com banco novo, evento perdido...)."""
    torres = db.query(Torre).all()
    for torre in torres:
        try:
            eventos.publicar("torre.sincronizada", torre.estado())
        except eventos.FalhaAoPublicar:
            raise HTTPException(503, "RabbitMQ indisponível.")
    return {"reenviadas": len(torres)}
