CREATE OR REPLACE TABLE gold_ipca_anual AS
SELECT
    year(mes) AS ano,
    round((product(1 + variacao / 100) - 1) * 100, 2) AS ipca
FROM silver_ipca_mensal
GROUP BY year(mes)
HAVING count(*) = 12
ORDER BY ano