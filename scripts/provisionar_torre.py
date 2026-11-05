"""Etapa de fabrica: cadastra uma placa e gera o adesivo com o codigo.

Uso (com a placa gravada e ligada no USB):

    export AUTH_API=https://<servico-de-auth>
    export ADMIN_API_KEY=...            # a mesma do .env do serviço de auth
    python scripts/provisionar_torre.py --kit pro --porta COM5        # Windows
    python scripts/provisionar_torre.py --kit completo --porta /dev/ttyUSB0

Sem a placa no USB, informe o id lido no monitor serial:

    python scripts/provisionar_torre.py --kit basico --torre-id AT-24DCC3A1B2C4

Só refazer o adesivo de uma torre já cadastrada, com o código que você já
tem (não chama o servidor, não desvincula ninguém):

    python scripts/provisionar_torre.py --kit pro --torre-id AT-24DCC3A1B2C4 --so-etiqueta K9X2-7QHM

O adesivo traz o guia completo: rede AeroTower-XXXX + senha (com QR que
conecta o celular), o endereço 192.168.4.1 e o código para o app. Se a
senha do portal não for "aerotower", passe --senha-wifi ou defina
SENHA_PORTAL_WIFI.

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


REDE_PORTAL_PREFIXO = "AeroTower-"
IP_PORTAL = "192.168.4.1"


def rede_portal(torre_id: str) -> str:
    """Mesmo nome que o firmware cria: "AeroTower-" + 4 últimos caracteres do id."""
    return REDE_PORTAL_PREFIXO + torre_id[-4:]


def _fonte(tamanho: int, negrito: bool = False):
    """Primeira fonte que existir (Linux, Windows, macOS); senão a embutida."""
    from PIL import ImageFont
    nomes = (["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "Helvetica-Bold.ttf"] if negrito
             else ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "Helvetica.ttf"])
    for nome in nomes:
        try:
            return ImageFont.truetype(nome, tamanho)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=tamanho)   # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def gerar_etiqueta(torre_id: str, kit: str, codigo: str, pasta: Path, senha_wifi: str) -> Path:
    """Adesivo com o guia completo: 1) Wi-Fi da torre, 2) código para o app.

    O QR do passo 1 conecta o celular na rede da torre só apontando a
    câmera (padrão WIFI: que Android e iPhone entendem).
    """
    destino = pasta / f"{torre_id}.png"
    try:
        import qrcode
        from PIL import Image, ImageDraw
    except ImportError:
        print("  (instale qrcode e Pillow para gerar o PNG: pip install qrcode pillow)")
        return None

    rede = rede_portal(torre_id)
    qr_wifi = qrcode.make(f"WIFI:T:WPA;S:{rede};P:{senha_wifi};;").resize((260, 260))

    larg, alt = 1200, 760
    img = Image.new("RGB", (larg, alt), "white")
    d = ImageDraw.Draw(img)
    titulo, sub = _fonte(46, True), _fonte(24)
    passo, texto, forte = _fonte(30, True), _fonte(25), _fonte(27, True)
    codigo_fonte, mini = _fonte(64, True), _fonte(20)

    # Cabeçalho
    d.text((40, 30), "AeroTower", fill="black", font=titulo)
    d.text((40, 88), f"Kit {kit}  ·  {torre_id}", fill="#555555", font=sub)
    d.line([(40, 135), (larg - 40, 135)], fill="#BBBBBB", width=2)
    d.line([(larg // 2, 160), (larg // 2, alt - 40)], fill="#DDDDDD", width=2)

    # Passo 1: Wi-Fi
    x1 = 40
    d.text((x1, 160), "1  Conecte a torre ao Wi-Fi", fill="black", font=passo)
    img.paste(qr_wifi, (x1, 210))
    d.text((x1 + 275, 225), "Aponte a câmera", fill="#555555", font=mini)
    d.text((x1 + 275, 250), "ou conecte na rede:", fill="#555555", font=mini)
    d.text((x1 + 275, 290), rede, fill="black", font=forte)
    d.text((x1 + 275, 340), "Senha:", fill="#555555", font=mini)
    d.text((x1 + 275, 365), senha_wifi, fill="black", font=forte)
    linhas = [
        f"Se a página não abrir sozinha,",
        f"acesse {IP_PORTAL} no navegador.",
        "Toque em Configure WiFi e escolha",
        "o Wi-Fi da casa (2,4 GHz).",
    ]
    for i, linha in enumerate(linhas):
        d.text((x1, 500 + i * 34), linha, fill="black", font=texto)
    d.text((x1, 650), f"Trocou de roteador? Segure BOOT por 5 s.", fill="#555555", font=mini)

    # Passo 2: app (o app ainda não lê QR, então o código vai grande)
    x2 = larg // 2 + 40
    d.text((x2, 160), "2  Vincule no app", fill="black", font=passo)
    d.text((x2, 225), "Código de ativação:", fill="#555555", font=mini)
    d.rounded_rectangle([(x2, 260), (larg - 40, 380)], radius=14, outline="black", width=3)
    d.text(((x2 + larg - 40) // 2, 320), codigo, fill="black", font=codigo_fonte, anchor="mm")
    for i, linha in enumerate(["Entre com o Google no app", "e toque em Adicionar torre.", "Digite o código acima."]):
        d.text((x2, 500 + i * 34), linha, fill="black", font=texto)
    d.text((x2, 650), "Guarde este adesivo: o código não", fill="#555555", font=mini)
    d.text((x2, 676), "pode ser recuperado depois.", fill="#555555", font=mini)

    img.save(destino)
    return destino


def _pasta() -> Path:
    pasta = Path("etiquetas")
    pasta.mkdir(exist_ok=True)
    return pasta


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--kit", choices=["basico", "completo", "pro"])
    origem = parser.add_mutually_exclusive_group(required=True)
    origem.add_argument("--porta", help="porta USB da placa (COM5, /dev/ttyUSB0)")
    origem.add_argument("--torre-id", help="id já conhecido, ex.: AT-24DCC3A1B2C4")
    parser.add_argument("--novo-codigo", action="store_true",
                        help="torre já cadastrada: desvincula o dono e gera outro código")
    parser.add_argument("--so-etiqueta", metavar="CODIGO",
                        help="só refaz o adesivo com um código que você já tem (não chama o servidor nem desvincula)")
    parser.add_argument("--senha-wifi", default=os.environ.get("SENHA_PORTAL_WIFI", "aerotower"),
                        help="senha da rede AeroTower-XXXX (SENHA_PORTAL_WIFI do segredos.h). Padrão: aerotower")
    args = parser.parse_args()

    torre_id = (args.torre_id or ler_id_pela_serial(args.porta)).upper()
    print(f"Torre: {torre_id}")

    if args.so_etiqueta:
        png = gerar_etiqueta(torre_id, args.kit or "pro", args.so_etiqueta.upper(), _pasta(), args.senha_wifi)
        if png:
            print(f"Etiqueta: {png}")
        return

    if args.novo_codigo:
        resposta = chamar_api("POST", f"/admin/torres/{torre_id}/novo-codigo")
    else:
        if not args.kit:
            sys.exit("Informe --kit para cadastrar uma torre nova.")
        resposta = chamar_api("POST", "/admin/torres", {"torreId": torre_id, "kit": args.kit})

    codigo, kit = resposta["codigoAtivacao"], resposta["kit"]
    print(f"Kit:    {kit}")
    print(f"Código: {codigo}   <- vai no adesivo")

    pasta = _pasta()
    png = gerar_etiqueta(torre_id, kit, codigo, pasta, args.senha_wifi)
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
