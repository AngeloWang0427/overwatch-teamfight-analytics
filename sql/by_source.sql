-- Unknown outcomes and durations are excluded from their own denominators only.
SELECT data_source, COALESCE(confidence, 'unrecorded') AS confidence, COUNT(*) AS n_fights,
       COUNT(DISTINCT match_id) AS n_matches,
       COUNT(fight_won) AS n_outcomes, SUM(fight_won) AS wins,
       AVG(fight_won) AS win_rate,
       COUNT(fight_duration) AS n_durations,
       AVG(fight_duration) AS mean_duration_sec
FROM fights
GROUP BY data_source, confidence
ORDER BY data_source, confidence;
