"""Marca cada teste com o tipo, pela pasta onde ele esta.

`pytest -m seguranca` roda so os de seguranca. No PyCharm, o mesmo filtro
vai em Run Configuration > Additional Arguments.
"""
from pathlib import Path

import pytest

_TIPO_POR_PASTA = {
    "unitarios":  "unitario",
    "integracao": "integracao",
    "funcionais": "funcional",
    "aceitacao":  "aceitacao",
    "desempenho": "desempenho",
    "seguranca":  "seguranca",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        tipo = _TIPO_POR_PASTA.get(Path(str(item.fspath)).parent.name)
        if tipo:
            item.add_marker(getattr(pytest.mark, tipo))
