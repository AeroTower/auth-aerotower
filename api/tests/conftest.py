import os
import sys
import tempfile
from pathlib import Path

_pasta = tempfile.mkdtemp()
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_pasta}/auth-teste.db",
    "JWT_SEGREDO": "segredo-de-teste",
    "ADMIN_API_KEY": "admin-teste",
    "AUTH_MODO_DEV": "true",
    "GOOGLE_CLIENT_IDS": "nosso-app.apps.googleusercontent.com",
    "MAX_TORRES_POR_USUARIO": "1",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def cliente_e_eventos(monkeypatch):
    import eventos
    import main

    publicados = []
    monkeypatch.setattr(eventos, "publicar", lambda tipo, torre: publicados.append((tipo, dict(torre))))
    with TestClient(main.app) as cliente:
        yield cliente, publicados
