CREATE OR REPLACE TABLE gold_focus_meta AS
WITH primeira AS (
    SELECT
        ano_ref,
        mediana,
        row_number() OVER (PARTITION BY ano_ref ORDER BY data) AS rn
    FROM silver_focus
    WHERE base_calculo = 0
        AND year(data) = ano_ref
)
SELECT
    a.ano,
    p.mediana AS mediana_inicio,
    m.meta,
    a.ipca
FROM gold_ipca_anual AS a
INNER JOIN primeira AS p
    ON p.ano_ref = a.ano
    AND p.rn = 1
LEFT JOIN silver_meta AS m
    ON m.ano = a.ano
ORDER BY a.ano