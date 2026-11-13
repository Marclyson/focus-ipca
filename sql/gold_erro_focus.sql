CREATE OR REPLACE TABLE gold_erro_focus AS
SELECT
    f.ano_ref,
    f.data,
    CAST(make_date(f.ano_ref, 12, 31) - f.data AS INTEGER) AS dias_ate_fim,
    f.mediana,
    a.ipca,
    round(f.mediana - a.ipca, 4) AS erro_pp
FROM silver_focus AS f
INNER JOIN gold_ipca_anual AS a
    ON f.ano_ref = a.ano
WHERE f.base_calculo = 0