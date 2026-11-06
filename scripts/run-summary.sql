-- Run from one experiment run folder, not a batch containing multiple runs.
WITH
advice AS (
    SELECT substr(turn.path, 1, length(turn.path) - length('/metadata.json')) AS attempt_path,
           score.content ->> 'score' AS score
    FROM './windows/*/forks/*/turns/*/metadata.json' AS turn
    JOIN './advices/*/advice.json' AS score
      ON score.path = (turn.content ->> 'advice') || '/advice.json'
),
sample_results AS (
    SELECT substr(path, 1, instr(path, '/ts/') - 1) AS attempt_path,
           content ->> 'passed' AS tests_passed,
           content ->> 'total' AS tests_total,
           content ->> 'all_passed' AS all_passed
    FROM './windows/*/forks/*/turns/*/ts/*/attempts/*/tests.json'
),
evaluations AS (
    SELECT attempt_path,
           coalesce((SELECT content ->> 't_samples' FROM settings), 1) AS expected,
           count(*) AS completed,
           sum(all_passed) AS passing_ts,
           CASE WHEN count(*) = coalesce((SELECT content ->> 't_samples' FROM settings), 1)
                THEN min(all_passed) END AS all_passed,
           sum(tests_passed) AS tests_passed,
           sum(tests_total) AS tests_total
    FROM sample_results
    GROUP BY attempt_path
),
paths AS (
    SELECT attempt_path FROM advice
    UNION SELECT attempt_path FROM evaluations
),
attempts AS (
    SELECT cast(substr(p.attempt_path, instr(p.attempt_path, '/turns/') + 7) AS integer) AS attempt_index,
           row_number() OVER (ORDER BY cast(substr(p.attempt_path, instr(p.attempt_path, 'windows/') + 8) AS integer),
                                       cast(substr(p.attempt_path, instr(p.attempt_path, '/turns/') + 7) AS integer),
                                       cast(substr(p.attempt_path, instr(p.attempt_path, '/forks/') + 7) AS integer)) AS attempt_order,
           a.score,
           e.tests_passed, e.tests_total,
           coalesce(e.completed, 0) AS completed_t_evaluations,
           CASE WHEN e.completed = e.expected THEN 1 ELSE 0 END AS completed_evaluation_attempts,
           e.passing_ts,
           e.all_passed,
           CASE WHEN e.all_passed = 1 THEN 'passed'
                WHEN e.all_passed = 0 THEN 'failed_tests'
                WHEN e.completed > 0 THEN 'incomplete_batch'
                ELSE 'not_evaluated' END AS outcome
    FROM paths p
    LEFT JOIN advice a USING (attempt_path)
    LEFT JOIN evaluations e USING (attempt_path)
),
run_metadata AS (
    SELECT content FROM './run.json'
),
settings AS (
    SELECT content FROM './settings.json'
),
result AS (
    SELECT content FROM './result.json'
),
rows AS (
    SELECT 'run' AS scope, NULL AS attempt_index,
           NULL AS score,
           coalesce(sum(completed_t_evaluations), 0) AS completed_t_evaluations,
           coalesce(sum(completed_evaluation_attempts), 0) AS completed_evaluation_attempts,
           coalesce(sum(passing_ts), 0) AS passing_ts,
           NULL AS tests_passed, NULL AS tests_total,
           CASE (SELECT content ->> 'success' FROM result)
               WHEN 1 THEN 'passed' WHEN 0 THEN 'failed_tests'
               ELSE 'no_final_result' END AS outcome
    FROM attempts
    UNION ALL
    SELECT 'attempt', attempt_index, score, completed_t_evaluations,
           completed_evaluation_attempts, passing_ts, tests_passed, tests_total, outcome
    FROM attempts
)
SELECT
    CASE WHEN EXISTS (SELECT 1 FROM settings)
         THEN (SELECT content ->> 'u_advice_max_chars' FROM settings)
         ELSE (SELECT content ->> '$.params."u-advice-max-chars"' FROM run_metadata) END AS cap,
    CASE WHEN EXISTS (SELECT 1 FROM settings)
         THEN CASE WHEN (SELECT content ->> 'u_advice_max_chars' FROM settings) IS NULL
                   THEN 'uncapped' ELSE 'recorded' END
         WHEN EXISTS (
        SELECT 1 FROM run_metadata, json_each(content, '$.params')
        WHERE key = 'u-advice-max-chars'
    ) THEN 'recorded' ELSE 'unknown' END AS cap_status,
    coalesce((SELECT content ->> 't_samples' FROM settings),
             (SELECT max(expected) FROM evaluations)) AS ts_per_advice,
    CASE WHEN EXISTS (SELECT 1 FROM evaluations WHERE all_passed = 1)
         THEN (SELECT count(*) FROM attempts WHERE completed_evaluation_attempts = 1
               AND attempt_order <= (SELECT min(attempt_order) FROM attempts WHERE all_passed = 1))
         END AS evaluation_attempts_to_success,
    rows.*
FROM rows
ORDER BY CASE scope WHEN 'run' THEN 0 ELSE 1 END, attempt_index;
