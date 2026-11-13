CREATE OR REPLACE TABLE gold_resumo_horizonte AS
WITH classificado AS (
    SELECT
        ano_ref,
        abs(erro_pp) AS erro_abs,
        CASE
            WHEN dias_ate_fim >= 730 THEN 1
            WHEN dias_ate_fim >= 365 THEN 2
            WHEN dias_ate_fim >= 182 THEN 3
            WHEN dias_ate_fim >= 91 THEN 4
            WHEN dias_ate_fim >= 0 THEN 5
        END AS ordem,
        CASE
            WHEN dias_ate_fim >= 730 THEN '24+ meses'
            WHEN dias_ate_fim >= 365 THEN '12 a 24 meses'
            WHEN dias_ate_fim >= 182 THEN '6 a 12 meses'
            WHEN dias_ate_fim >= 91 THEN '3 a 6 meses'
            WHEN dias_ate_fim >= 0 THEN 'até 3 meses'
        END AS faixa
    FROM gold_erro_focus
    WHERE dias_ate_fim >= 0
)
SELECT
    faixa,
    ordem,
    round(avg(erro_abs), 2) AS erro_abs_medio,
    round(median(erro_abs), 2) AS erro_abs_mediano,
    count(DISTINCT ano_ref) AS n_anos
FROM classificado
WHERE ordem IS NOT NULL
GROUP BY faixa, ordem
ORDER BY ordem