CREATE OR REPLACE TABLE silver_meta AS
SELECT
    year(strptime(data, '%d/%m/%Y'))::INTEGER AS ano,
    valor::DOUBLE AS meta
FROM bronze_sgs
WHERE codigo = 13521
QUALIFY row_number() OVER (
    PARTITION BY data
    ORDER BY _data_extracao DESC, _hash_linha DESC
) = 1