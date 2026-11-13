import json
from datetime import date, datetime
from pathlib import Path

import duckdb
import pytest

from focus_ipca import extrair, transformar

FIXTURES = Path(__file__).parent / "fixtures"
PASTA_SQL = Path(__file__).resolve().parent.parent / "sql"
DATA_EXTRACAO = datetime(2024, 12, 3, 12, 0, 0)
DATA_EXTRACAO_TARDE = datetime(2024, 12, 4, 12, 0, 0)


def carregar_fixture(nome):
    with open(FIXTURES / nome, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def linhas_focus():
    return carregar_fixture("focus_pagina_1.json")["value"] + carregar_fixture("focus_pagina_2.json")["value"]


def carregar_amostras_sgs(con):
    extrair.carregar_sgs(con, 433, carregar_fixture("sgs_433.json"), DATA_EXTRACAO)
    extrair.carregar_sgs(con, 13521, carregar_fixture("sgs_13521.json"), DATA_EXTRACAO)


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


@pytest.fixture
def con():
    conexao = duckdb.connect(":memory:")
    extrair.criar_tabelas(conexao)
    yield conexao
    conexao.close()


def rodar(con):
    transformar.transformar(con, str(PASTA_SQL))


def test_gold_ipca_anual(con):
    carregar_amostras_sgs(con)
    rodar(con)
    valores = dict(con.execute("SELECT ano, ipca FROM gold_ipca_anual").fetchall())
    assert valores[2023] == pytest.approx(4.62)
    assert valores[2024] == pytest.approx(4.83)


def test_silver_focus_e_unica_e_usa_a_versao_mais_recente(con):
    linhas = linhas_focus()
    extrair.carregar_focus(con, linhas, DATA_EXTRACAO)
    alterada = dict(linhas[0])
    alterada["Mediana"] = alterada["Mediana"] + 1
    extrair.carregar_focus(con, [alterada], DATA_EXTRACAO_TARDE)
    rodar(con)

    total, distintos = con.execute(
        "SELECT count(*), count(DISTINCT (data, ano_ref, base_calculo)) FROM silver_focus"
    ).fetchone()
    assert total == distintos == 10

    mediana = con.execute(
        "SELECT mediana FROM silver_focus WHERE data = ? AND ano_ref = ? AND base_calculo = ?",
        [linhas[0]["Data"], int(linhas[0]["DataReferencia"]), linhas[0]["baseCalculo"]],
    ).fetchone()[0]
    assert mediana == pytest.approx(alterada["Mediana"])


def test_gold_erro_focus_2024(con):
    extrair.carregar_focus(con, linhas_focus(), DATA_EXTRACAO)
    carregar_amostras_sgs(con)
    rodar(con)

    resultado = con.execute(
        """
        SELECT mediana, erro_pp, dias_ate_fim
        FROM gold_erro_focus
        WHERE ano_ref = 2024 AND data = DATE '2024-12-02'
        """
    ).fetchall()
    assert len(resultado) == 1
    mediana, erro_pp, dias_ate_fim = resultado[0]
    assert mediana == pytest.approx(4.7275)
    assert erro_pp == pytest.approx(-0.1025)
    assert dias_ate_fim == 29


def test_transformar_duas_vezes_mesmo_conteudo(con):
    extrair.carregar_focus(con, linhas_focus(), DATA_EXTRACAO)
    carregar_amostras_sgs(con)
    rodar(con)
    antes = {
        tabela: con.execute(f"SELECT * FROM {tabela} ORDER BY ALL").fetchall()
        for tabela in transformar.TABELAS
    }
    rodar(con)
    depois = {
        tabela: con.execute(f"SELECT * FROM {tabela} ORDER BY ALL").fetchall()
        for tabela in transformar.TABELAS
    }
    assert antes == depois


def test_gold_convergencia_dados_sinteticos(con):
    carregar_amostras_sgs(con)
    extrair.carregar_focus(
        con,
        [
            linha_focus("2023-01-02", 2023, 6.0),
            linha_focus("2023-06-01", 2023, 5.3),
            linha_focus("2023-10-02", 2023, 4.7),
        ],
        DATA_EXTRACAO,
    )
    rodar(con)

    resultado = con.execute(
        "SELECT ano_ref, data_convergencia, erro_inicial_pp FROM gold_convergencia WHERE ano_ref = 2023"
    ).fetchall()
    assert len(resultado) == 1
    ano_ref, data_convergencia, erro_inicial_pp = resultado[0]
    assert ano_ref == 2023
    assert data_convergencia == date(2023, 10, 2)
    assert erro_inicial_pp == pytest.approx(1.38)


def test_gold_resumo_horizonte_ordem_e_sem_dias_negativos(con):
    carregar_amostras_sgs(con)
    extrair.carregar_focus(
        con,
        [
            linha_focus("2022-12-01", 2024, 9.0),
            linha_focus("2023-06-01", 2024, 8.0),
            linha_focus("2024-06-03", 2024, 6.0),
            linha_focus("2024-10-01", 2024, 5.5),
            linha_focus("2024-12-20", 2024, 5.0),
            linha_focus("2025-01-05", 2024, 9.9),
        ],
        DATA_EXTRACAO,
    )
    rodar(con)

    assert con.execute("SELECT count(*) FROM gold_erro_focus WHERE dias_ate_fim < 0").fetchone()[0] == 1

    resultado = con.execute(
        "SELECT faixa, ordem, erro_abs_medio, erro_abs_mediano, n_anos FROM gold_resumo_horizonte"
    ).fetchall()
    assert [linha[1] for linha in resultado] == [1, 2, 3, 4, 5]
    assert [linha[0] for linha in resultado] == [
        "24+ meses",
        "12 a 24 meses",
        "6 a 12 meses",
        "3 a 6 meses",
        "até 3 meses",
    ]
    assert all(linha[2] == pytest.approx(linha[3]) for linha in resultado)
    assert [linha[2] for linha in resultado] == pytest.approx([4.17, 3.17, 1.17, 0.67, 0.17])
    assert all(linha[4] == 1 for linha in resultado)

def test_gold_focus_meta_usa_a_primeira_projecao_dentro_do_ano(con):
    carregar_amostras_sgs(con)
    extrair.carregar_focus(
        con,
        [linha_focus("2022-06-01", 2023, 3.5), linha_focus("2023-01-02", 2023, 5.3), linha_focus("2023-06-01", 2023, 6.0)],
        DATA_EXTRACAO,
    )
    rodar(con)
    linha = con.execute("SELECT mediana_inicio, meta, ipca FROM gold_focus_meta WHERE ano = 2023").fetchone()
    assert linha == (pytest.approx(5.3), pytest.approx(3.25), pytest.approx(4.62))
