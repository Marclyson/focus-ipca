"""Exporta o painel do Focus x IPCA em JSON e HTML autocontido."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
MODELO = RAIZ / "painel" / "modelo.html"


def _converter(valor):
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return valor


def _linhas(con, sql):
    cursor = con.execute(sql)
    nomes = [descrição[0] for descrição in cursor.description]
    return [{nome: _converter(valor) for nome, valor in zip(nomes, linha)} for linha in cursor.fetchall()]


def _um_valor(con, sql):
    return con.execute(sql).fetchone()[0]


def gerar_dados(con):
    """Monta o dicionário JSON-serializável com os dados do painel."""
    ipca_anual = _linhas(
        con,
        """
        SELECT a.ano, a.ipca, m.meta
        FROM gold_ipca_anual AS a
        LEFT JOIN (
            SELECT ano, max(meta) AS meta
            FROM silver_meta
            GROUP BY ano
        ) AS m ON m.ano = a.ano
        WHERE a.ano >= 2000
        ORDER BY a.ano
        """,
    )

    curvas = {}
    for linha in _linhas(
        con,
        """
        SELECT
            CAST(ano_ref AS VARCHAR) AS ano_ref,
            dias_ate_fim,
            erro_pp
        FROM (
            SELECT ano_ref, data, dias_ate_fim, erro_pp
            FROM gold_erro_focus
            QUALIFY row_number() OVER (
                PARTITION BY ano_ref, year(data), month(data)
                ORDER BY data DESC
            ) = 1
        )
        WHERE dias_ate_fim >= 0
        ORDER BY ano_ref, dias_ate_fim DESC
        """,
    ):
        curvas.setdefault(linha["ano_ref"], []).append([linha["dias_ate_fim"], linha["erro_pp"]])

    convergencia = _linhas(
        con,
        """
        SELECT
            ano_ref,
            CAST(data_convergencia AS VARCHAR) AS data_convergencia,
            dias_antes_do_fim,
            erro_inicial_pp
        FROM gold_convergencia
        ORDER BY ano_ref
        """,
    )

    horizontes = _linhas(
        con,
        """
        SELECT faixa, ordem, erro_abs_medio, erro_abs_mediano, n_anos
        FROM gold_resumo_horizonte
        ORDER BY ordem
        """,
    )

    focus_meta = _linhas(
        con,
        """
        SELECT ano, mediana_inicio, meta, ipca
        FROM gold_focus_meta
        ORDER BY ano
        """,
    )

    erro_12_24 = _um_valor(
        con,
        """
        SELECT (
            SELECT erro_abs_medio
            FROM gold_resumo_horizonte
            WHERE faixa = '12 a 24 meses'
        )
        """,
    )
    erro_ate_3 = _um_valor(
        con,
        """
        SELECT (
            SELECT erro_abs_medio
            FROM gold_resumo_horizonte
            WHERE faixa = 'até 3 meses'
        )
        """,
    )
    maior = _linhas(
        con,
        """
        SELECT ano_ref, erro_inicial_pp
        FROM gold_convergencia
        ORDER BY abs(erro_inicial_pp) DESC
        LIMIT 1
        """,
    )

    resumo = {
        "anos": _um_valor(con, "SELECT count(DISTINCT ano_ref) FROM gold_convergencia"),
        "erro_12_24": erro_12_24,
        "erro_ate_3": erro_ate_3,
        "dias_convergencia_mediana": _um_valor(
            con, "SELECT median(dias_antes_do_fim) FROM gold_convergencia"
        ),
        "maior_erro_ano": maior[0]["ano_ref"] if maior else None,
        "maior_erro_pp": maior[0]["erro_inicial_pp"] if maior else None,
    }

    return {
        "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ipca_anual": ipca_anual,
        "curvas": curvas,
        "convergencia": convergencia,
        "horizontes": horizontes,
        "focus_meta": focus_meta,
        "resumo": resumo,
    }


def montar_html(modelo: str, dados: dict) -> str:
    """Substitui o marcador de dados do modelo pelo JSON serializado."""
    return modelo.replace("/*DADOS*/", json.dumps(dados, ensure_ascii=False))


def main():
    caminho = os.environ.get("FOCUS_IPCA_DB", "dados/focus_ipca.duckdb")
    con = duckdb.connect(caminho)
    try:
        dados = gerar_dados(con)
    finally:
        con.close()

    saida = Path(os.environ.get("FOCUS_IPCA_PAINEL", "painel"))
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "dados.json").write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    modelo = MODELO.read_text(encoding="utf-8")
    (saida / "index.html").write_text(montar_html(modelo, dados), encoding="utf-8")


if __name__ == "__main__":
    main()