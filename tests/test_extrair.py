import json
import urllib.parse
from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from focus_ipca import extrair

FIXTURES = Path(__file__).parent / "fixtures"
DATA_EXTRACAO = datetime(2024, 12, 3, 12, 0, 0)


def carregar_fixture(nome):
    with open(FIXTURES / nome, encoding="utf-8") as arquivo:
        return json.load(arquivo)


@pytest.fixture
def con():
    conexao = duckdb.connect(":memory:")
    extrair.criar_tabelas(conexao)
    yield conexao
    conexao.close()


def test_url_focus_tem_pagina_e_filtro_sem_count():
    url = extrair.url_focus("2024-12-02", 10000, 100)
    decodificada = urllib.parse.unquote(url)
    assert "$skip=10000" in url
    assert "$top=100" in url
    assert "Data ge '2024-12-02'" in decodificada
    assert "$count" not in url


def test_paginar_focus_pagina_ate_a_primeira_vazia():
    pagina_1 = carregar_fixture("focus_pagina_1.json")
    pagina_2 = carregar_fixture("focus_pagina_2.json")
    pagina_vazia = carregar_fixture("focus_pagina_vazia.json")
    chamadas = []

    def baixar_falso(url):
        chamadas.append(url)
        skip = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["$skip"][0]
        if skip == "0":
            return pagina_1
        if skip == "5":
            return pagina_2
        return pagina_vazia

    linhas = extrair.paginar_focus("2024-12-02", top=5, baixar=baixar_falso)
    assert len(linhas) == 10
    assert len(chamadas) == 3


def test_carregar_focus_nao_duplica(con):
    linhas = carregar_fixture("focus_pagina_1.json")["value"] + carregar_fixture("focus_pagina_2.json")["value"]
    assert extrair.carregar_focus(con, linhas, DATA_EXTRACAO) == 10
    assert extrair.carregar_focus(con, linhas, DATA_EXTRACAO) == 0


def test_mediana_alterada_vira_linha_nova(con):
    linhas = carregar_fixture("focus_pagina_1.json")["value"] + carregar_fixture("focus_pagina_2.json")["value"]
    assert extrair.carregar_focus(con, linhas, DATA_EXTRACAO) == 10
    alterada = dict(linhas[0])
    alterada["Mediana"] = alterada["Mediana"] + 1
    assert extrair.carregar_focus(con, [alterada], DATA_EXTRACAO) == 1
    total = con.execute("SELECT count(*) FROM bronze_focus").fetchone()[0]
    assert total == 11


def test_carregar_sgs_nao_duplica(con):
    linhas = carregar_fixture("sgs_433.json")
    assert extrair.carregar_sgs(con, 433, linhas, DATA_EXTRACAO) == 24
    assert extrair.carregar_sgs(con, 433, linhas, DATA_EXTRACAO) == 0


def test_data_inicial_focus(con):
    assert extrair.data_inicial_focus(con) == "2000-01-01"
    linhas = carregar_fixture("focus_pagina_1.json")["value"] + carregar_fixture("focus_pagina_2.json")["value"]
    extrair.carregar_focus(con, linhas, DATA_EXTRACAO)
    assert extrair.data_inicial_focus(con) == "2024-10-28"