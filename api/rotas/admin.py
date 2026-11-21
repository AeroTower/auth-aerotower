"""Rotas da fabrica (script provisionar_torre.py). Exigem X-Admin-Key."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import regras_torre
from banco import get_db
from dependencias import exigir_admin
from schemas import CadastrarTorreSchema

router = APIRouter(prefix="/admin", tags=["Fábrica (admin)"], dependencies=[Depends(exigir_admin)])


@router.post("/torres", status_code=201)
def cadastrar_torre(data: CadastrarTorreSchema, db: Session = Depends(get_db)):
    torre, codigo = regras_torre.cadastrar(db, data.torreId, data.kit)
    return {"torreId": torre.id, "kit": torre.kit, "codigoAtivacao": codigo}


@router.post("/torres/{torre_id}/novo-codigo")
def novo_codigo(torre_id: str, db: Session = Depends(get_db)):
    """Adesivo perdido ou torre devolvida: desvincula e troca o codigo."""
    torre, codigo = regras_torre.trocar_codigo(db, torre_id)
    return {"torreId": torre.id, "kit": torre.kit, "codigoAtivacao": codigo}


@router.get("/torres")
def listar_torres(db: Session = Depends(get_db)):
    return [
        {**t.estado(), "vinculadaEm": t.vinculada_em, "criadaEm": t.criada_em}
        for t in regras_torre.listar_todas(db)
    ]


@router.post("/sincronizar")
def sincronizar(db: Session = Depends(get_db)):
    """Reenvia o estado de todas as torres (Backend com banco novo, evento perdido...)."""
    return {"reenviadas": regras_torre.reenviar_todas(db)}
