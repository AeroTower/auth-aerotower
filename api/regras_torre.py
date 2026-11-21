"""Regras de negocio das torres: vinculo, desvinculo e cadastro de fabrica.

Nada aqui conhece HTTP. Cada regra quebrada vira um erro de `erros.py`,
que o main.py traduz para o status certo.
"""
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

import codigo as codigos
import eventos
from banco import Torre, Usuario
from config import MAX_TORRES_POR_USUARIO
from erros import (
    CodigoInvalido,
    DadoInvalido,
    EventoNaoEntregue,
    LimiteDeTorres,
    TorreDeOutroDono,
    TorreJaCadastrada,
    TorreNaoEncontrada,
)


def torres_do_usuario(db: Session, usuario_id: str) -> List[Torre]:
    return db.query(Torre).filter(Torre.dono_id == usuario_id).order_by(Torre.vinculada_em).all()


def _publicar_ou_desfazer(db: Session, tipo: str, torre: Torre) -> None:
    """Grava so se o evento chegou ao RabbitMQ; senao, desfaz e avisa o app.

    Assim banco e Backend nao ficam discordando em silencio. (Ainda resta a
    janela minuscula de o commit falhar depois da publicacao; o reenvio em
    /admin/sincronizar corrige. O padrao "outbox" resolveria de vez.)
    """
    db.flush()
    try:
        eventos.publicar(tipo, torre.estado())
    except eventos.FalhaAoPublicar as erro:
        db.rollback()
        raise EventoNaoEntregue(
            "Serviço temporariamente indisponível. Tente de novo em instantes.") from erro
    db.commit()


# ── Vinculo (app) ─────────────────────────────────────────────

def vincular(db: Session, usuario: Usuario, codigo: str, apelido: Optional[str]) -> Tuple[Torre, bool]:
    """Liga a torre do adesivo a quem esta logado. Devolve (torre, ja_era_sua)."""
    if not codigos.valido(codigo):
        raise CodigoInvalido()
    torre = db.query(Torre).filter(Torre.codigo_hash == codigos.hash_de(codigo)).first()
    if torre is None:
        raise CodigoInvalido()

    if torre.dono_id == usuario.id:   # repetiu o pedido: tudo certo
        return torre, True

    # REGRA DE NEGOCIO 1: limite de torres por usuario (hoje 1)
    atuais = torres_do_usuario(db, usuario.id)
    if len(atuais) >= MAX_TORRES_POR_USUARIO:
        raise LimiteDeTorres(f"Você já possui a torre '{atuais[0].apelido or atuais[0].id}' vinculada.")

    # REGRA DE NEGOCIO 2: a torre ja tem dono?
    if torre.dono_id is not None:
        raise TorreDeOutroDono()

    # UPDATE condicional: se duas pessoas usarem o mesmo codigo ao mesmo
    # tempo, so uma encontra dono_id ainda vazio.
    alteradas = (
        db.query(Torre)
        .filter(Torre.id == torre.id, Torre.dono_id.is_(None))
        .update({
            Torre.dono_id: usuario.id,
            Torre.apelido: (apelido or "").strip() or None,
            Torre.vinculada_em: datetime.now(),
            Torre.versao: Torre.versao + 1,
        }, synchronize_session=False)
    )
    if alteradas == 0:
        db.rollback()
        raise TorreDeOutroDono()
    db.refresh(torre)
    _publicar_ou_desfazer(db, "torre.vinculada", torre)
    return torre, False


def desvincular(db: Session, usuario: Usuario, torre_id: str) -> None:
    torre = db.get(Torre, torre_id.upper())
    if torre is None or torre.dono_id != usuario.id:
        raise TorreNaoEncontrada()
    torre.dono_id, torre.apelido, torre.vinculada_em = None, None, None
    torre.versao += 1
    _publicar_ou_desfazer(db, "torre.desvinculada", torre)


# ── Fabrica (admin) ───────────────────────────────────────────

def cadastrar(db: Session, torre_id: str, kit: str) -> Tuple[Torre, str]:
    """Cadastra a placa e devolve (torre, codigo do adesivo). O banco guarda so o hash."""
    torre_id = torre_id.strip().upper()
    if not codigos.id_torre_valido(torre_id):
        raise DadoInvalido("Id de torre inválido. Use AT-<MAC>, ex.: AT-24DCC3A1B2C4.")
    if kit not in codigos.KITS:
        raise DadoInvalido(f"Kit inválido. Use um de: {', '.join(codigos.KITS)}.")
    if db.get(Torre, torre_id) is not None:
        raise TorreJaCadastrada(f"A torre {torre_id} já está cadastrada.")

    codigo = codigos.gerar()
    torre = Torre(id=torre_id, kit=kit, codigo_hash=codigos.hash_de(codigo), versao=1)
    db.add(torre)
    _publicar_ou_desfazer(db, "torre.cadastrada", torre)
    return torre, codigo


def trocar_codigo(db: Session, torre_id: str) -> Tuple[Torre, str]:
    """Adesivo perdido ou torre devolvida: desvincula e troca o codigo."""
    torre = db.get(Torre, torre_id.upper())
    if torre is None:
        raise TorreNaoEncontrada()
    codigo = codigos.gerar()
    torre.codigo_hash = codigos.hash_de(codigo)
    torre.dono_id, torre.apelido, torre.vinculada_em = None, None, None
    torre.versao += 1
    _publicar_ou_desfazer(db, "torre.desvinculada", torre)
    return torre, codigo


def listar_todas(db: Session) -> List[Torre]:
    return db.query(Torre).order_by(Torre.criada_em).all()


def reenviar_todas(db: Session) -> int:
    """Reenvia o estado de todas as torres (Backend com banco novo, evento perdido...)."""
    torres = db.query(Torre).all()
    for torre in torres:
        try:
            eventos.publicar("torre.sincronizada", torre.estado())
        except eventos.FalhaAoPublicar as erro:
            # "unroutable" = nenhuma fila ligada: o worker nunca conectou
            # neste broker (confira RABBITMQ_URL no worker e na API).
            raise EventoNaoEntregue(f"Evento não publicado no RabbitMQ: {erro}") from erro
    return len(torres)
