"""Testes de aceitacao (BDD) da historia "vincular a torre com o codigo do adesivo"."""
from pytest_bdd import given, parsers, scenarios, then, when

from apoio import login, nova_torre

scenarios("vincular_torre.feature")


@given(parsers.parse('uma torre do kit "{kit}" saiu da fábrica com um adesivo'), target_fixture="cenario")
def torre_da_fabrica(cliente_e_eventos, kit):
    cliente, eventos = cliente_e_eventos
    torre, codigo = nova_torre(cliente, kit)
    return {"cliente": cliente, "eventos": eventos, "torre": torre, "codigo": codigo}


@given("a Ana entrou no app com a conta Google dela")
def ana_entra(cenario):
    cenario["ana"], _ = login(cenario["cliente"])


@given("que o Bruno já vinculou essa torre")
def bruno_vinculou(cenario):
    cenario["bruno"], _ = login(cenario["cliente"])
    _vincular(cenario, "bruno", cenario["codigo"])


@given("que a Ana já tem outra torre vinculada")
def ana_tem_outra(cenario):
    _, outro_codigo = nova_torre(cenario["cliente"], "basico")
    assert _vincular(cenario, "ana", outro_codigo).status_code == 200


@given("que a Ana vinculou a torre")
def ana_vinculou(cenario):
    assert _vincular(cenario, "ana", cenario["codigo"]).status_code == 200


def _vincular(cenario, quem, codigo, apelido=None):
    corpo = {"codigo": codigo, **({"apelido": apelido} if apelido else {})}
    cenario["resposta"] = cenario["cliente"].post("/torre/vincular", json=corpo, headers=cenario[quem])
    return cenario["resposta"]


@when(parsers.parse('a Ana digita o código do adesivo com o apelido "{apelido}"'))
def ana_digita(cenario, apelido):
    _vincular(cenario, "ana", cenario["codigo"], apelido)


@when("a Ana digita o código em minúsculas e sem o hífen")
def ana_digita_minusculo(cenario):
    _vincular(cenario, "ana", cenario["codigo"].lower().replace("-", ""))


@when("a Ana desvincula a torre")
def ana_desvincula(cenario):
    r = cenario["cliente"].delete(f"/torre/{cenario['torre']}/vinculo", headers=cenario["ana"])
    assert r.status_code == 200


@when("o Bruno digita o mesmo código do adesivo")
def bruno_digita(cenario):
    cenario["bruno"], _ = login(cenario["cliente"])
    _vincular(cenario, "bruno", cenario["codigo"])


def _torres(cenario, quem):
    return cenario["cliente"].get("/auth/me", headers=cenario[quem]).json()["torres"]


@then(parsers.parse('a torre aparece na conta da Ana com o apelido "{apelido}"'))
def aparece_com_apelido(cenario, apelido):
    assert _torres(cenario, "ana") == [{"id": cenario["torre"], "kit": "pro", "apelido": apelido}]


@then("a torre aparece na conta da Ana")
def aparece_ana(cenario):
    assert [t["id"] for t in _torres(cenario, "ana")] == [cenario["torre"]]


@then("a torre aparece na conta do Bruno")
def aparece_bruno(cenario):
    assert [t["id"] for t in _torres(cenario, "bruno")] == [cenario["torre"]]


@then("o Backend é avisado de que a torre foi vinculada")
def backend_avisado(cenario):
    tipo, estado = cenario["eventos"][-1]
    assert tipo == "torre.vinculada" and estado["id"] == cenario["torre"] and estado["donoId"]


@then(parsers.parse('a Ana vê a mensagem "{trecho}"'))
def ve_mensagem(cenario, trecho):
    assert cenario["resposta"].status_code in (400, 409)
    assert trecho in cenario["resposta"].json()["detail"]
