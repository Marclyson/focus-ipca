CREATE OR REPLACE TABLE silver_ipca_mensal AS
SELECT
    strptime(data, '%d/%m/%Y')::DATE AS mes,
    valor::DOUBLE AS variacao
FROM bronze_sgs
WHERE codigo = 433
QUALIFY row_number() OVER (
    PARTITION BY data
    ORDER BY _data_extracao DESC, _hash_linha DESC
) = 1