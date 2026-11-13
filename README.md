# Focus x IPCA

Quanto o mercado erra a inflação, e com quanto tempo de antecedência ele acerta.

## Como rodar

- `make install`
- `make carga`
- `make painel`
- `make test`

## Dados

Boletim Focus e séries do SGS (IPCA, código 433; meta de inflação, código 13521), do Banco Central do Brasil, licença ODbL; o IPCA é produzido pelo IBGE; código sob MIT.

## Como manter

- A carga é incremental: pede ao Focus só os últimos 35 dias além do que já tem, e um valor republicado vira linha nova no bronze, sem apagar o anterior.
- A primeira carga completa leva alguns minutos por causa da API do Banco Central.
- A CI roda o pipeline duas vezes numa amostra real em `tests/fixtures` e falha se o resultado mudar.