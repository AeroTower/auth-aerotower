"""Tabela-resumo dos testes por tipo, em Markdown (evidencia para o relatorio).

Uso, depois de rodar o pytest com --junitxml e --cov-report=xml:

    pytest --cov --cov-report=xml --junitxml=relatorio-testes.xml
    python .github/resumo_testes.py relatorio-testes.xml coverage.xml

No GitHub Actions a saida vai para o resumo da execucao (aba Actions).
"""
import sys
import xml.etree.ElementTree as ET
from collections import Counter

TIPOS = {
    "unitarios": "Unitário",
    "integracao": "Integração",
    "funcionais": "Funcional",
    "aceitacao": "Aceitação",
    "desempenho": "Desempenho",
    "seguranca": "Segurança",
}


def contar(junit):
    total, falhas = Counter(), Counter()
    for caso in ET.parse(junit).iter("testcase"):
        partes = caso.get("classname", "").split(".")
        tipo = next((TIPOS[p] for p in partes if p in TIPOS), "Outros")
        total[tipo] += 1
        if caso.find("failure") is not None or caso.find("error") is not None:
            falhas[tipo] += 1
    return total, falhas


def main(junit, cobertura=None):
    total, falhas = contar(junit)
    linhas = ["| Tipo | Testes | Passaram | Falharam |", "|---|---:|---:|---:|"]
    for tipo in list(TIPOS.values()) + ["Outros"]:
        if total[tipo]:
            linhas.append(f"| {tipo} | {total[tipo]} | {total[tipo] - falhas[tipo]} | {falhas[tipo]} |")
    soma, soma_falhas = sum(total.values()), sum(falhas.values())
    linhas.append(f"| **Total** | **{soma}** | **{soma - soma_falhas}** | **{soma_falhas}** |")
    if cobertura:
        taxa = float(ET.parse(cobertura).getroot().get("line-rate", 0)) * 100
        linhas += ["", f"**Cobertura de código:** {taxa:.1f}% (meta: 90%)"]
    print("\n".join(linhas))


if __name__ == "__main__":
    main(*sys.argv[1:3])
