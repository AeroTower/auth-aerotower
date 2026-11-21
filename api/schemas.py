"""Formato dos pedidos que a API recebe (validados pelo Pydantic)."""
from typing import Optional

from pydantic import BaseModel, Field, model_validator


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
