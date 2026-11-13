"""Extrai as séries do Boletim Focus e do SGS do Banco Central (camada bronze)."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import duckdb

BASE_FOCUS = (
    "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
)
USER_AGENT = "focus-ipca/0.1"
TIMEOUT = 60
TENTATIVAS = 3
ESPERA = 5


def baixar_json(url):
    """GET com User-Agent próprio, timeout e até 3 tentativas."""
    ultimo_erro = None
    for tentativa in range(TENTATIVAS):
        try:
            pedido = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(pedido, timeout=TIMEOUT) as resposta:
                corpo = resposta.read()
            return json.loads(corpo.decode("utf-8"))
        except Exception as erro:  # noqa: BLE001 - tenta novamente em qualquer falha de rede
            ultimo_erro = erro
            if tentativa < TENTATIVAS - 1:
                time.sleep(ESPERA)
    raise ultimo_erro


def url_sgs(codigo):
    return f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json"


def url_focus(data_inicial, skip, top):
    filtro = f"Indicador eq 'IPCA' and Data ge '{data_inicial}'"
    ordem = "Data asc,DataReferencia asc,baseCalculo asc"
    seguro = "$=,'()"
    partes = [
        f"$filter={urllib.parse.quote(filtro, safe=seguro)}",
        f"$orderby={urllib.parse.quote(ordem, safe=seguro)}",
        "$format=json",
        f"$top={top}",
        f"$skip={skip}",
    ]
    return f"{BASE_FOCUS}?{'&'.join(partes)}"


def paginar_focus(data_inicial, top=10000, baixar=baixar_json):
    linhas = []
    skip = 0
    while True:
        pagina = baixar(url_focus(data_inicial, skip, top))
        valores = pagina.get("value", []) if isinstance(pagina, dict) else []
        if not valores:
            break
        linhas.extend(valores)
        skip += top
    return linhas


def criar_tabelas(con):
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS bronze_sgs (
            codigo INTEGER,
            data VARCHAR,
            valor VARCHAR,
            _data_extracao TIMESTAMP,
            _hash_linha VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS bronze_focus (
            Indicador VARCHAR,
            Data VARCHAR,
            DataReferencia VARCHAR,
            Media DOUBLE,
            Mediana DOUBLE,
            DesvioPadrao DOUBLE,
            Minimo DOUBLE,
            Maximo DOUBLE,
            numeroRespondentes INTEGER,
            baseCalculo INTEGER,
            _data_extracao TIMESTAMP,
            _hash_linha VARCHAR
        )
        """
    )


def hash_linha(linha: dict) -> str:
    dados = {chave: valor for chave, valor in linha.items() if chave != "IndicadorDetalhe"}
    return hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _hashes_sgs(con, codigo):
    registros = con.execute("SELECT _hash_linha FROM bronze_sgs WHERE codigo = ?", [codigo]).fetchall()
    return {registro[0] for registro in registros}


def carregar_sgs(con, codigo, linhas, data_extracao):
    existentes = _hashes_sgs(con, codigo)
    novas = []
    for linha in linhas:
        completo = {"codigo": codigo, **linha}
        resumo = hash_linha(completo)
        if resumo in existentes:
            continue
        existentes.add(resumo)
        novas.append((codigo, linha.get("data"), linha.get("valor"), data_extracao, resumo))
    if novas:
        con.executemany(
            "INSERT INTO bronze_sgs VALUES (?, ?, ?, ?, ?)",
            novas,
        )
    return len(novas)


def carregar_focus(con, linhas, data_extracao):
    registros = con.execute("SELECT _hash_linha FROM bronze_focus").fetchall()
    existentes = {registro[0] for registro in registros}
    novas = []
    for linha in linhas:
        resumo = hash_linha(linha)
        if resumo in existentes:
            continue
        existentes.add(resumo)
        novas.append(
            (
                linha.get("Indicador"),
                linha.get("Data"),
                linha.get("DataReferencia"),
                linha.get("Media"),
                linha.get("Mediana"),
                linha.get("DesvioPadrao"),
                linha.get("Minimo"),
                linha.get("Maximo"),
                linha.get("numeroRespondentes"),
                linha.get("baseCalculo"),
                data_extracao,
                resumo,
            )
        )
    if novas:
        con.executemany(
            "INSERT INTO bronze_focus VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            novas,
        )
    return len(novas)


def data_inicial_focus(con):
    maior = con.execute("SELECT max(Data) FROM bronze_focus").fetchone()[0]
    if not maior:
        return "2000-01-01"
    data = datetime.strptime(str(maior), "%Y-%m-%d").date()
    return (data - timedelta(days=35)).strftime("%Y-%m-%d")


def main():
    caminho = os.environ.get("FOCUS_IPCA_DB", "dados/focus_ipca.duckdb")
    pasta = os.path.dirname(caminho)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    con = duckdb.connect(caminho)
    try:
        criar_tabelas(con)
        data_extracao = datetime.now()
        for codigo in (433, 13521):
            linhas = baixar_json(url_sgs(codigo))
            inseridas = carregar_sgs(con, codigo, linhas, data_extracao)
            print(f"SGS {codigo}: {inseridas} linhas novas")
        inicio = data_inicial_focus(con)
        linhas = paginar_focus(inicio)
        inseridas = carregar_focus(con, linhas, data_extracao)
        print(f"Focus desde {inicio}: {inseridas} linhas novas")
    finally:
        con.close()


if __name__ == "__main__":
    main()