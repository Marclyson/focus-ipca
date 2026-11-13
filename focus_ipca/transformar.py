"""Transforma os dados brutos em tabelas para o painel."""

from __future__ import annotations

import os
from pathlib import Path

import duckdb

ORDEM = [
    "silver_focus.sql",
    "silver_ipca_mensal.sql",
    "silver_meta.sql",
    "gold_ipca_anual.sql",
    "gold_erro_focus.sql",
    "gold_convergencia.sql",
    "gold_resumo_horizonte.sql",
    "gold_focus_meta.sql",
]

TABELAS = [nome[: -len(".sql")] for nome in ORDEM]


def transformar(con, pasta_sql="sql"):
    """Executa os CREATE OR REPLACE TABLE de cada arquivo de ``pasta_sql``, em ordem."""
    base = Path(pasta_sql)
    for nome in ORDEM:
        sql = (base / nome).read_text(encoding="utf-8")
        con.execute(sql)


def main():
    caminho = os.environ.get("FOCUS_IPCA_DB", "dados/focus_ipca.duckdb")
    pasta = os.path.dirname(caminho)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    con = duckdb.connect(caminho)
    try:
        transformar(con)
        for tabela in TABELAS:
            total = con.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0]
            print(f"{tabela}: {total}")
    finally:
        con.close()


if __name__ == "__main__":
    main()