-- H1: pre-fight readiness; retain fights with missing outcomes in n_fights.
SELECT data_source, COALESCE(confidence, 'unrecorded') AS confidence, ult_diff, COUNT(*) AS n_fights,
       COUNT(DISTINCT match_id) AS n_matches,
       COUNT(fight_won) AS n_outcomes, SUM(fight_won) AS wins,
       AVG(fight_won) AS win_rate
FROM fights
WHERE ult_diff IS NOT NULL
GROUP BY data_source, confidence, ult_diff
ORDER BY data_source, confidence, ult_diff;
