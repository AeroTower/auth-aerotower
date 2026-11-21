import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import regras_torre
from banco import Torre, Usuario, get_db
from dependencias import usuario_logado
from schemas import VincularTorreSchema

logger = logging.getLogger("auth")
router = APIRouter(tags=["Vínculo da torre"])


def _resposta_vinculo(torre: Torre, mensagem: str) -> dict:
    return {
        "status":   "success",
        "message":  mensagem,
        "torre_id": torre.id,
        "kit":      torre.kit,
        "apelido":  torre.apelido,
    }


@router.post("/torre/vincular")
def vincular_torre(
    data: VincularTorreSchema,
    usuario: Usuario = Depends(usuario_logado),
    db: Session = Depends(get_db),
):
    # Quem vincula e quem esta logado. Antes o e-mail vinha no corpo e
    # qualquer pessoa podia vincular uma torre ao e-mail de outra.
    torre, ja_era_sua = regras_torre.vincular(db, usuario, data.codigo_informado, data.apelido)
    if ja_era_sua:
        return _resposta_vinculo(torre, "Esta torre já está vinculada a você.")
    logger.info("Torre %s vinculada a %s", torre.id, usuario.id)
    return _resposta_vinculo(torre, "Torre vinculada com sucesso!")


@router.delete("/torre/{torre_id}/vinculo", summary="Desvincula a torre da conta (para passar adiante)")
def desvincular(torre_id: str, usuario: Usuario = Depends(usuario_logado), db: Session = Depends(get_db)):
    regras_torre.desvincular(db, usuario, torre_id)
    return {"status": "success", "message": "Torre desvinculada. O código do adesivo volta a valer."}
