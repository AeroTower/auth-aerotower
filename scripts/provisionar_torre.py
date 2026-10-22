"""Etapa de fabrica: cadastra uma placa e gera o adesivo com o codigo.

Uso (com a placa gravada e ligada no USB):

    export AUTH_API=https://<servico-de-auth>
    export ADMIN_API_KEY=...            # a mesma do .env do serviço de auth
    python scripts/provisionar_torre.py --kit pro --porta COM5        # Windows
    python scripts/provisionar_torre.py --kit completo --porta /dev/ttyUSB0

Sem a placa no USB, informe o id lido no monitor serial:

    python scripts/provisionar_torre.py --kit basico --torre-id AT-24DCC3A1B2C4

Saida: etiquetas/<torre_id>.png (adesivo com QR e codigo) e uma linha em
etiquetas/torres.csv (sem o codigo). O codigo em texto so existe no
adesivo: o servidor guarda apenas o hash. Perdeu o adesivo? Use
--novo-codigo.

Dependencias opcionais: pyserial (ler a porta USB), qrcode e Pillow (PNG).
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PADRAO_ID = re.compile(r"TORRE_ID=(AT-[0-9A-F]{12})")


def ler_id_pela_serial(porta: str, segundos: int = 15) -> str:
    try:
        import serial  # pyserial
    except ImportError:
        sys.exit("Instale o pyserial (pip install pyserial) ou use --torre-id.")

    with serial.Serial(porta, 115200, timeout=1) as conexao:
        # Pulsa o reset da placa para ela imprimir o cabecalho de novo.
        conexao.dtr = False
        conexao.rts = True
        time.sleep(0.1)
        conexao.rts = False
        limite = time.time() + segundos
        while time.time() < limite:
            linha = conexao.readline().decode("utf-8", errors="ignore")
            achado = PADRAO_ID.search(linha)
            if achado:
                return achado.group(1)
    sys.exit(f"Não encontrei TORRE_ID na porta {porta} em {segundos}s. A placa está gravada com o firmware v2?")


def chamar_api(metodo: str, caminho: str, corpo=None) -> dict:
    base = os.environ.get("AUTH_API", "").rstrip("/")
    chave = os.environ.get("ADMIN_API_KEY", "")
    if not base or not chave:
        sys.exit("Defina AUTH_API e ADMIN_API_KEY no ambiente.")
    dados = json.dumps(corpo).encode() if corpo is not None else None
    pedido = urllib.request.Request(
        base + caminho, data=dados, method=metodo,
        headers={"Content-Type": "application/json", "X-Admin-Key": chave},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=60) as resposta:
            return json.loads(resposta.read())
    except urllib.error.HTTPError as erro:
        sys.exit(f"Servidor respondeu {erro.code}: {erro.read().decode(errors='ignore')}")


def gerar_etiqueta(torre_id: str, kit: str, codigo: str, pasta: Path) -> Path:
    destino = pasta / f"{torre_id}.png"
    try:
        import qrcode
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  (instale qrcode e Pillow para gerar o PNG: pip install qrcode pillow)")
        return None

    qr = qrcode.make(codigo).resize((300, 300))
    img = Image.new("RGB", (900, 360), "white")
    img.paste(qr, (30, 30))
    desenho = ImageDraw.Draw(img)
    try:
        grande = ImageFont.truetype("DejaVuSans-Bold.ttf", 64)
        media  = ImageFont.truetype("DejaVuSans.ttf", 30)
    except OSError:
        grande = media = ImageFont.load_default()
    desenho.text((360, 50),  "AeroTower", fill="black", font=media)
    desenho.text((360, 110), codigo, fill="black", font=grande)
    desenho.text((360, 210), f"Kit {kit}", fill="black", font=media)
    desenho.text((360, 260), "No app: Adicionar torre", fill="black", font=media)
    img.save(destino)
    return destino


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--kit", choices=["basico", "completo", "pro"])
    origem = parser.add_mutually_exclusive_group(required=True)
    origem.add_argument("--porta", help="porta USB da placa (COM5, /dev/ttyUSB0)")
    origem.add_argument("--torre-id", help="id já conhecido, ex.: AT-24DCC3A1B2C4")
    parser.add_argument("--novo-codigo", action="store_true",
                        help="torre já cadastrada: desvincula o dono e gera outro código")
    args = parser.parse_args()

    torre_id = (args.torre_id or ler_id_pela_serial(args.porta)).upper()
    print(f"Torre: {torre_id}")

    if args.novo_codigo:
        resposta = chamar_api("POST", f"/admin/torres/{torre_id}/novo-codigo")
    else:
        if not args.kit:
            sys.exit("Informe --kit para cadastrar uma torre nova.")
        resposta = chamar_api("POST", "/admin/torres", {"torreId": torre_id, "kit": args.kit})

    codigo, kit = resposta["codigoAtivacao"], resposta["kit"]
    print(f"Kit:    {kit}")
    print(f"Código: {codigo}   <- vai no adesivo")

    pasta = Path("etiquetas")
    pasta.mkdir(exist_ok=True)
    png = gerar_etiqueta(torre_id, kit, codigo, pasta)
    if png:
        print(f"Etiqueta: {png}")

    registro = pasta / "torres.csv"
    novo = not registro.exists()
    with registro.open("a", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        if novo:
            escritor.writerow(["torre_id", "kit", "data", "acao"])
        escritor.writerow([torre_id, kit, datetime.now().isoformat(timespec="seconds"),
                           "novo-codigo" if args.novo_codigo else "cadastro"])


if __name__ == "__main__":
    main()
