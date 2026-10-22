"""Codigo do adesivo e id da torre."""
import hashlib
import re
import secrets

ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # sem 0/O, 1/I/L: a pessoa digita
TAMANHO = 8
KITS = ("basico", "completo", "pro")
_ID_TORRE = re.compile(r"^AT-[0-9A-Z]{4,16}$")


def gerar() -> str:
    bruto = "".join(secrets.choice(ALFABETO) for _ in range(TAMANHO))
    return f"{bruto[:4]}-{bruto[4:]}"


def normalizar(codigo: str) -> str:
    return "".join(c for c in (codigo or "").upper() if c.isalnum())


def valido(codigo: str) -> bool:
    limpo = normalizar(codigo)
    return len(limpo) == TAMANHO and all(c in ALFABETO for c in limpo)


def hash_de(codigo: str) -> str:
    return hashlib.sha256(normalizar(codigo).encode()).hexdigest()


def id_torre_valido(torre_id: str) -> bool:
    return bool(_ID_TORRE.match(torre_id or ""))
