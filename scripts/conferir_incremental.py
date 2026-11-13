"""Confere que rodar o pipeline duas vezes sobre a mesma amostra não muda o resultado."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from focus_ipca import exportar, extrair, transformar


def tabelas(con):
    registros = con.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND (table_name LIKE 'silver_%' OR table_name LIKE 'gold_%')
        ORDER BY table_name
        """
    ).fetchall()
    return [registro[0] for registro in registros]


def conteudo(con, tabela):
    cursor = con.execute(f'SELECT * FROM "{tabela}" ORDER BY ALL')
    linhas = []
    for linha in cursor.fetchall():
        linhas.append("|".join("NULL" if valor is None else str(valor) for valor in linha))
    return len(linhas), "\n".join(linhas)


def resumo(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def rodar(caminho):
    extrair.main()
    transformar.main()
    exportar.main()
    con = duckdb.connect(caminho)
    try:
        return {tabela: conteudo(con, tabela) for tabela in tabelas(con)}
    finally:
        con.close()


def main():
    os.chdir(RAIZ)
    with tempfile.TemporaryDirectory(prefix="focus-ipca-ci-") as temporario:
        caminho = str(Path(temporario) / "focus_ipca.duckdb")
        os.environ["FOCUS_IPCA_DB"] = caminho
        os.environ["FOCUS_IPCA_AMOSTRA"] = str(RAIZ / "tests" / "fixtures")
        os.environ["FOCUS_IPCA_PAINEL"] = str(Path(temporario) / "painel")
        primeira = rodar(caminho)
        segunda = rodar(caminho)

    falhas = []
    for tabela in sorted(primeira):
        contagem = segunda[tabela][0]
        print(f"{tabela}: {contagem}")
        if tabela.startswith("gold_") and contagem == 0:
            falhas.append(f"{tabela} está vazia")
        if resumo(primeira[tabela][1]) != resumo(segunda[tabela][1]):
            falhas.append(f"{tabela} mudou entre as duas rodadas")

    for falha in falhas:
        print(f"falha: {falha}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())