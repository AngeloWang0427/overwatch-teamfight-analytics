WITH observations AS (
    SELECT data_source, confidence, 'ult_diff' AS variable, ult_diff AS value FROM fights
    UNION ALL
    SELECT data_source, confidence, 'first_pick', first_pick FROM fights
    UNION ALL
    SELECT data_source, confidence, 'fight_won', fight_won FROM fights
    UNION ALL
    SELECT data_source, confidence, 'fight_duration', fight_duration FROM fights
)
SELECT data_source, COALESCE(confidence, 'unrecorded') AS confidence, variable, COUNT(*) AS n_fights,
       COUNT(value) AS n_known, COUNT(*) - COUNT(value) AS n_missing
FROM observations
GROUP BY data_source, confidence, variable
ORDER BY data_source, confidence, variable;
