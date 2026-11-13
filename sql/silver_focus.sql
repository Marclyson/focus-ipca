CREATE OR REPLACE TABLE silver_focus AS
SELECT
    CAST(Data AS DATE) AS data,
    CAST(DataReferencia AS INTEGER) AS ano_ref,
    baseCalculo AS base_calculo,
    Media AS media,
    Mediana AS mediana,
    DesvioPadrao AS desvio,
    Minimo AS minimo,
    Maximo AS maximo,
    numeroRespondentes AS respondentes
FROM bronze_focus
WHERE Indicador = 'IPCA'
QUALIFY row_number() OVER (
    PARTITION BY Data, DataReferencia, baseCalculo
    ORDER BY _data_extracao DESC, _hash_linha DESC
) = 1