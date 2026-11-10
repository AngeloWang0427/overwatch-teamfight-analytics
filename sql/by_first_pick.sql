-- During-fight descriptive association, never a pre-fight predictor.
SELECT data_source, COALESCE(confidence, 'unrecorded') AS confidence, first_pick, COUNT(*) AS n_fights,
       COUNT(DISTINCT match_id) AS n_matches,
       COUNT(fight_won) AS n_outcomes, SUM(fight_won) AS wins,
       AVG(fight_won) AS win_rate
FROM fights
WHERE first_pick IS NOT NULL
GROUP BY data_source, confidence, first_pick
ORDER BY data_source, confidence, first_pick;
