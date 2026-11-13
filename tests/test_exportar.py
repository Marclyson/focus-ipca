import json
from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from focus_ipca import exportar, extrair, transformar

RAIZ = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
PASTA_SQL = RAIZ / "sql"
MODELO = RAIZ / "painel" / "modelo.html"
DATA_EXTRACAO = datetime(2024, 12, 3, 12, 0, 0)


def carregar_fixture(nome):
    with open(FIXTURES / nome, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def linha_focus(data, ano_ref, mediana):
    return {
        "Indicador": "IPCA",
        "Data": data,
        "DataReferencia": str(ano_ref),
        "Media": mediana,
        "Mediana": mediana,
        "DesvioPadrao": 0.0,
        "Minimo": mediana,
        "Maximo": mediana,
        "numeroRespondentes": 1,
        "baseCalculo": 0,
    }


def popular(con):
    extrair.carregar_sgs(con, 433, carregar_fixture("sgs_433.json"), DATA_EXTRACAO)
    extrair.carregar_sgs(con, 13521, carregar_fixture("sgs_13521.json"), DATA_EXTRACAO)
    linhas = carregar_fixture("focus_pagina_1.json")["value"] + carregar_fixture("focus_pagina_2.json")["value"]
    extrair.carregar_focus(con, linhas, DATA_EXTRACAO)
    extrair.carregar_focus(
        con,
        [
            linha_focus("2024-01-10", 2024, 5.0),
            linha_focus("2024-01-20", 2024, 5.2),
            linha_focus("2024-06-03", 2024, 4.5),
        ],
        DATA_EXTRACAO,
    )
    transformar.transformar(con, str(PASTA_SQL))


def criar_conexao():
    conexao = duckdb.connect(":memory:")
    extrair.criar_tabelas(conexao)
    popular(conexao)
    return conexao


def test_gerar_dados_tem_as_chaves_e_serializa_em_json():
    con = criar_conexao()
    try:
        dados = exportar.gerar_dados(con)
    finally:
        con.close()

    for chave in ("gerado_em", "ipca_anual", "curvas", "convergencia", "horizontes", "focus_meta", "resumo"):
        assert chave in dados
    json.dumps(dados)
    assert isinstance(dados["curvas"], dict)


def test_curvas_tem_um_ponto_por_mes_e_ordem_decrescente():
    con = criar_conexao()
    try:
        dados = exportar.gerar_dados(con)
    finally:
        con.close()

    curva = dados["curvas"]["2024"]
    janeiro = [ponto for ponto in curva if 335 <= ponto[0] <= 365]
    assert len(janeiro) == 1
    assert janeiro[0] == [346, pytest.approx(0.37)]
    assert all(curva[indice][0] > curva[indice + 1][0] for indice in range(len(curva) - 1))


def test_montar_html_substitui_o_marcador_sem_recursos_externos():
    con = criar_conexao()
    try:
        dados = exportar.gerar_dados(con)
    finally:
        con.close()

    html = exportar.montar_html(MODELO.read_text(encoding="utf-8"), dados)
    assert "/*DADOS*/" not in html
    assert '"ipca_anual"' in html
    assert "<script src" not in html
    assert "http://" not in html
    assert "https://fonts" not in html