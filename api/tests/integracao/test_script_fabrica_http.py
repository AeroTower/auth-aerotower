"""Integracao script de fabrica <-> API, por HTTP de verdade.

Sobe a API num servidor uvicorn local e roda o `provisionar_torre.py` como
na fabrica. So o RabbitMQ e trocado por um duble.
"""
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import provisionar_torre  # noqa: E402


def _porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def api_no_ar(monkeypatch):
    import eventos
    import main

    publicados = []
    monkeypatch.setattr(eventos, "publicar", lambda tipo, torre: publicados.append((tipo, dict(torre))))
    porta = _porta_livre()
    servidor = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=porta, log_level="warning"))
    thread = threading.Thread(target=servidor.run, daemon=True)
    thread.start()
    limite = time.time() + 10
    while not servidor.started and time.time() < limite:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{porta}", publicados
    servidor.should_exit = True
    thread.join(timeout=5)


def test_fabrica_cadastra_gera_adesivo_e_troca_codigo(api_no_ar, monkeypatch, tmp_path):
    url, publicados = api_no_ar
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AUTH_API", url)
    monkeypatch.setenv("ADMIN_API_KEY", "admin-teste")
    torre = "AT-24DCC3A1B2C4"

    monkeypatch.setattr(sys, "argv", ["provisionar_torre.py", "--kit", "completo", "--torre-id", torre.lower()])
    provisionar_torre.main()
    assert publicados[-1][0] == "torre.cadastrada" and publicados[-1][1]["kit"] == "completo"
    assert (tmp_path / "etiquetas" / f"{torre}.png").exists()

    monkeypatch.setattr(sys, "argv", ["provisionar_torre.py", "--torre-id", torre, "--novo-codigo"])
    provisionar_torre.main()
    assert publicados[-1][0] == "torre.desvinculada"

    linhas = (tmp_path / "etiquetas" / "torres.csv").read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "torre_id,kit,data,acao"
    assert [l.split(",")[3] for l in linhas[1:]] == ["cadastro", "novo-codigo"]
    # o codigo em texto nunca vai para o CSV (so existe no adesivo)
    assert all(len(l.split(",")) == 4 for l in linhas)


def test_fabrica_com_chave_errada_para_com_mensagem(api_no_ar, monkeypatch):
    url, _ = api_no_ar
    monkeypatch.setenv("AUTH_API", url)
    monkeypatch.setenv("ADMIN_API_KEY", "chave-errada")
    with pytest.raises(SystemExit, match="403"):
        provisionar_torre.chamar_api("POST", "/admin/torres", {"torreId": "AT-AAAA0001", "kit": "pro"})
