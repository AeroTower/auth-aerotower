import pytest
from datetime import datetime, timedelta, timezone
import jwt
import sessao

def test_emitir_e_validar_sessao_com_sucesso():
    token = sessao.emitir("usuario_123", "teste@dominio.pt")
    sub = sessao.validar(token)
    assert sub == "usuario_123"

def test_validar_rejeita_token_expirado():
    # Força a criação de um token vencido no passado
    token = jwt.encode(
        {
            "sub": "usr",
            "iss": sessao.JWT_EMISSOR,
            "aud": sessao.JWT_AUDIENCIA,
            "exp": datetime.now(timezone.utc) - timedelta(days=1)
        },
        sessao._SEGREDO,
        algorithm="HS256"
    )
    with pytest.raises(sessao.SessaoInvalida, match="expirada"):
        sessao.validar(token)

def test_validar_rejeita_token_forjado():
    with pytest.raises(sessao.SessaoInvalida, match="inválida"):
        sessao.validar("ey...token.falso")