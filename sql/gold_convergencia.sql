CREATE OR REPLACE TABLE gold_convergencia AS
WITH numerado AS (
    SELECT
        ano_ref,
        data,
        dias_ate_fim,
        erro_pp,
        row_number() OVER (PARTITION BY ano_ref ORDER BY data) AS rn
    FROM gold_erro_focus
),
marcado AS (
    SELECT
        numerado.*,
        max(CASE WHEN abs(erro_pp) >= 0.5 THEN rn END) OVER (PARTITION BY ano_ref) AS ultima_acima,
        count(*) OVER (PARTITION BY ano_ref) AS total
    FROM numerado
),
alvo AS (
    SELECT DISTINCT
        ano_ref,
        ultima_acima,
        total,
        coalesce(ultima_acima, 0) + 1 AS rn_convergencia
    FROM marcado
),
inicial AS (
    SELECT ano_ref, erro_pp AS erro_inicial_pp
    FROM marcado
    WHERE rn = 1
),
convergente AS (
    SELECT
        m.ano_ref,
        m.data AS data_convergencia,
        m.dias_ate_fim AS dias_antes_do_fim
    FROM marcado AS m
    INNER JOIN alvo AS a
        ON m.ano_ref = a.ano_ref
        AND m.rn = a.rn_convergencia
)
SELECT
    a.ano_ref,
    c.data_convergencia,
    c.dias_antes_do_fim,
    i.erro_inicial_pp
FROM alvo AS a
INNER JOIN inicial AS i
    ON a.ano_ref = i.ano_ref
LEFT JOIN convergente AS c
    ON a.ano_ref = c.ano_ref
ORDER BY a.ano_ref