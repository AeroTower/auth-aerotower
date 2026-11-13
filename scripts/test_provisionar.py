import pytest
import sys
from pathlib import Path
    
# Adiciona a pasta scripts ao path temporariamente
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from provisionar_torre import rede_portal, PADRAO_ID

def test_rede_portal_extrai_ultimos_quatro_digitos():
    assert rede_portal("AT-24DCC3A1B2C4") == "AeroTower-B2C4"
    assert rede_portal("AT-1234") == "AeroTower-1234"

def test_padrao_id_regex_captura_mac_corretamente():
    linha_serial = "Iniciando boot... TORRE_ID=AT-24DCC3A1B2C4 (OK)"
    achado = PADRAO_ID.search(linha_serial)
    assert achado is not None
    assert achado.group(1) == "AT-24DCC3A1B2C4"