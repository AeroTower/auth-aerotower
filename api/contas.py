"""Contas de usuario: gravar quem entrou e montar a resposta do login."""
from typing import Optional

from sqlalchemy.orm import Session

import sessao
from banco import Usuario
from regras_torre import torres_do_usuario


def salvar_usuario(db: Session, sub: str, email: Optional[str], nome: Optional[str]) -> Usuario:
    """Cria a conta no primeiro login e atualiza nome e e-mail nos seguintes."""
    usuario = db.get(Usuario, sub)
    if usuario is None:
        usuario = Usuario(id=sub)
        db.add(usuario)
    usuario.email, usuario.nome = email, nome
    db.commit()
    return usuario


def resposta_login(db: Session, usuario: Usuario) -> dict:
    torres = torres_do_usuario(db, usuario.id)
    return {
        "status":       "success",
        "token":        sessao.emitir(usuario.id, usuario.email),
        "usuario":      {"id": usuario.id, "email": usuario.email, "nome": usuario.nome},
        # Campos que o app ja usava:
        "email":        usuario.email,
        "possui_torre": bool(torres),
        "torre_id":     torres[0].id if torres else None,
    }
