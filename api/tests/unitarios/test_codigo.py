import pytest
from codigo import gerar, normalizar, valido, hash_de, id_torre_valido, TAMANHO

def test_gerar_retorna_formato_correto():
    codigo = gerar()
    assert len(codigo) == TAMANHO + 1  # 8 letras + 1 hífen
    assert "-" in codigo
    assert valido(codigo)

def test_normalizar_remove_hifen_e_espacos():
    assert normalizar(" aB-cd 12 ") == "ABCD12"
    assert normalizar(None) == ""

def test_valido_rejeita_codigos_errados():
    assert valido("K9X2-7QHM") is True
    assert valido("K9X27QHM") is True  # Válido sem hífen (é normalizado)
    assert valido("K9X2-7QH") is False # Muito curto
    assert valido("K9X2-70HM") is False # Contém '0' (não está no alfabeto permitido)

def test_hash_de_gera_sha256_consistente():
    assert hash_de("ab-cd-1234") == hash_de("ABCD1234")
    assert len(hash_de("ABC")) == 64

def test_id_torre_valido():
    assert id_torre_valido("AT-1A2B3C4D5E6F") is True
    assert id_torre_valido("AT-1A2") is False # Curto demais
    assert id_torre_valido("BT-1A2B3C") is False # Prefixo errado