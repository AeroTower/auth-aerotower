"""Testes unitarios do script de fabrica (porta USB e servidor trocados por dubles)."""
import builtins
import io
import json
import sys
import types
import urllib.error

import pytest

import provisionar_torre as fab


# ── Leitura do id pela porta USB ─────────────────────────────

class SerialFalsa:
    def __init__(self, linhas):
        self._linhas = [linha.encode() for linha in linhas]
        self.dtr = self.rts = None

    def __call__(self, porta, baud, timeout):
        assert baud == 115200
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def readline(self):
        return self._linhas.pop(0) if self._linhas else b""


def _pyserial(monkeypatch, linhas):
    modulo = types.ModuleType("serial")
    modulo.Serial = SerialFalsa(linhas)
    monkeypatch.setitem(sys.modules, "serial", modulo)
    monkeypatch.setattr(fab.time, "sleep", lambda s: None)


def test_le_o_id_que_o_firmware_imprime(monkeypatch):
    _pyserial(monkeypatch, ["ets Jun  8 2016\r\n", "TORRE_ID=AT-24DCC3A1B2C4\r\n"])
    assert fab.ler_id_pela_serial("COM5") == "AT-24DCC3A1B2C4"


def test_placa_sem_firmware_v2_para_com_mensagem(monkeypatch):
    _pyserial(monkeypatch, ["lixo\r\n"])
    with pytest.raises(SystemExit, match="Não encontrei TORRE_ID"):
        fab.ler_id_pela_serial("COM5", segundos=0.05)


def test_sem_pyserial_instalado(monkeypatch):
    original = builtins.__import__

    def sem_serial(nome, *a, **k):
        if nome == "serial":
            raise ImportError(nome)
        return original(nome, *a, **k)

    monkeypatch.delitem(sys.modules, "serial", raising=False)
    monkeypatch.setattr(builtins, "__import__", sem_serial)
    with pytest.raises(SystemExit, match="pyserial"):
        fab.ler_id_pela_serial("COM5")


# ── Chamada ao servidor ──────────────────────────────────────

def test_sem_endereco_ou_chave_nao_chama_nada(monkeypatch):
    monkeypatch.delenv("AUTH_API", raising=False)
    monkeypatch.setenv("ADMIN_API_KEY", "x")
    with pytest.raises(SystemExit, match="AUTH_API"):
        fab.chamar_api("GET", "/admin/torres")


def test_chamada_monta_cabecalho_e_corpo(monkeypatch):
    monkeypatch.setenv("AUTH_API", "https://auth.exemplo/")
    monkeypatch.setenv("ADMIN_API_KEY", "segredo")
    pedidos = []

    class Resposta(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(pedido, timeout):
        pedidos.append(pedido)
        return Resposta(b'{"ok": true}')

    monkeypatch.setattr(fab.urllib.request, "urlopen", urlopen)
    assert fab.chamar_api("POST", "/admin/torres", {"kit": "pro"}) == {"ok": True}
    pedido = pedidos[0]
    assert pedido.full_url == "https://auth.exemplo/admin/torres"
    assert pedido.get_header("X-admin-key") == "segredo"
    assert json.loads(pedido.data) == {"kit": "pro"}


def test_erro_do_servidor_vira_mensagem(monkeypatch):
    monkeypatch.setenv("AUTH_API", "https://auth.exemplo")
    monkeypatch.setenv("ADMIN_API_KEY", "segredo")

    def urlopen(pedido, timeout):
        raise urllib.error.HTTPError(pedido.full_url, 409, "Conflict", {}, io.BytesIO(b"ja cadastrada"))

    monkeypatch.setattr(fab.urllib.request, "urlopen", urlopen)
    with pytest.raises(SystemExit, match="409: ja cadastrada"):
        fab.chamar_api("POST", "/admin/torres", {})


# ── Adesivo ──────────────────────────────────────────────────

def test_adesivo_e_gerado_em_png(tmp_path):
    from PIL import Image
    png = fab.gerar_etiqueta("AT-24DCC3A1B2C4", "pro", "K9X2-7QHM", tmp_path, "aerotower")
    assert png == tmp_path / "AT-24DCC3A1B2C4.png"
    assert Image.open(png).size == (1200, 760)


def test_sem_qrcode_instalado_so_avisa(monkeypatch, tmp_path, capsys):
    original = builtins.__import__

    def sem_qrcode(nome, *a, **k):
        if nome == "qrcode":
            raise ImportError(nome)
        return original(nome, *a, **k)

    monkeypatch.setattr(builtins, "__import__", sem_qrcode)
    assert fab.gerar_etiqueta("AT-24DCC3A1B2C4", "pro", "K9X2-7QHM", tmp_path, "x") is None
    assert "pip install qrcode" in capsys.readouterr().out


def test_fonte_cai_na_embutida_quando_nao_acha_nenhuma(monkeypatch):
    from PIL import ImageFont
    original = ImageFont.truetype

    def nenhuma(fonte, tamanho, **kw):
        if isinstance(fonte, str):          # nenhum arquivo de fonte no sistema
            raise OSError(fonte)
        return original(fonte, tamanho, **kw)   # a embutida do Pillow vem em bytes

    monkeypatch.setattr(ImageFont, "truetype", nenhuma)
    assert fab._fonte(20) is not None

    def pillow_antigo(size=None):
        if size is not None:
            raise TypeError("size")
        return "fonte-padrao"

    monkeypatch.setattr(ImageFont, "load_default", pillow_antigo)
    assert fab._fonte(20, negrito=True) == "fonte-padrao"


# ── Linha de comando ─────────────────────────────────────────

def _rodar(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["provisionar_torre.py", *args])
    fab.main()


def test_so_etiqueta_nao_chama_o_servidor(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fab, "chamar_api", lambda *a: pytest.fail("não devia chamar o servidor"))
    _rodar(monkeypatch, "--torre-id", "AT-24DCC3A1B2C4", "--so-etiqueta", "k9x2-7qhm")
    assert (tmp_path / "etiquetas" / "AT-24DCC3A1B2C4.png").exists()
    assert "Etiqueta:" in capsys.readouterr().out


def test_cadastro_sem_kit_para(monkeypatch):
    with pytest.raises(SystemExit, match="--kit"):
        _rodar(monkeypatch, "--torre-id", "AT-24DCC3A1B2C4")


def test_cadastro_pela_porta_usb(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fab, "ler_id_pela_serial", lambda porta: "AT-24DCC3A1B2C4")
    monkeypatch.setattr(fab, "gerar_etiqueta", lambda *a: None)     # sem Pillow nesta maquina
    chamadas = []
    monkeypatch.setattr(fab, "chamar_api", lambda metodo, caminho, corpo=None: (
        chamadas.append((metodo, caminho, corpo)) or {"codigoAtivacao": "K9X2-7QHM", "kit": "basico"}))
    _rodar(monkeypatch, "--kit", "basico", "--porta", "COM5")
    assert chamadas == [("POST", "/admin/torres", {"torreId": "AT-24DCC3A1B2C4", "kit": "basico"})]
    saida = capsys.readouterr().out
    assert "K9X2-7QHM" in saida and "Etiqueta" not in saida
