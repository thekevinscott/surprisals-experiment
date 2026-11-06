WITH
settings AS (
    SELECT coalesce((SELECT content ->> 't_samples' FROM './settings.json'), 1) AS ts_per_advice,
           coalesce((SELECT content ->> 't_sample_retries' FROM './settings.json'), 0) + 1 AS timeouts
),
tested AS (
    SELECT ts.turn_id, min(test_results.passed) AS passed,
           sum(test_results.passed) AS tests_passed, count(*) AS tests_total
    FROM ts JOIN test_results ON test_results.t_id = ts.id
    GROUP BY ts.id
    UNION ALL
    SELECT turn_id, 0, NULL, NULL FROM t_attempts WHERE timed_out
    GROUP BY turn_id, sample HAVING count(*) >= (SELECT timeouts FROM settings)
),
evaluations AS (
    SELECT turn_id, count(*) AS completed, sum(passed) AS passing_ts,
           CASE WHEN count(*) = (SELECT ts_per_advice FROM settings) THEN min(passed) END AS all_passed,
           sum(tests_passed) AS tests_passed, sum(tests_total) AS tests_total
    FROM tested
    GROUP BY turn_id
),
attempts AS (
    SELECT row_number() OVER (ORDER BY windows.position, turns.position, forks.position) - 1 AS attempt_index,
           windows.position AS window, forks.position AS fork, turns.position AS turn,
           advices.score,
           e.tests_passed, e.tests_total,
           coalesce(e.completed, 0) AS completed_t_evaluations,
           CASE WHEN e.completed = (SELECT ts_per_advice FROM settings) THEN 1 ELSE 0 END AS completed_evaluation_attempts,
           e.passing_ts,
           e.all_passed,
           CASE WHEN e.all_passed = 1 THEN 'passed'
                WHEN e.all_passed = 0 THEN 'failed_tests'
                WHEN e.completed > 0 THEN 'incomplete_batch'
                ELSE 'not_evaluated' END AS outcome
    FROM windows
    JOIN forks ON forks.window_id = windows.id
    JOIN turns ON turns.fork_id = forks.id
    LEFT JOIN turn_advice ON turn_advice.turn_id = turns.id
    LEFT JOIN advices ON advices.id = turn_advice.advice_id
    LEFT JOIN evaluations e ON e.turn_id = turns.id
),
rows AS (
    SELECT 'run' AS scope, NULL AS attempt_index, NULL AS window, NULL AS fork, NULL AS turn,
           NULL AS score,
           coalesce(sum(completed_t_evaluations), 0) AS completed_t_evaluations,
           coalesce(sum(completed_evaluation_attempts), 0) AS completed_evaluation_attempts,
           coalesce(sum(passing_ts), 0) AS passing_ts,
           NULL AS tests_passed, NULL AS tests_total,
           CASE (SELECT content ->> 'success' FROM './result.json')
               WHEN 1 THEN 'passed' WHEN 0 THEN 'failed_tests'
               ELSE 'no_final_result' END AS outcome
    FROM attempts
    UNION ALL
    SELECT 'attempt', attempt_index, window, fork, turn, score, completed_t_evaluations,
           completed_evaluation_attempts, passing_ts, tests_passed, tests_total, outcome
    FROM attempts
)
SELECT
    (SELECT ts_per_advice FROM settings) AS ts_per_advice,
    CASE WHEN EXISTS (SELECT 1 FROM attempts WHERE all_passed = 1)
         THEN (SELECT count(*) FROM attempts WHERE completed_evaluation_attempts = 1
               AND attempt_index <= (SELECT min(attempt_index) FROM attempts WHERE all_passed = 1))
         END AS evaluation_attempts_to_success,
    rows.*
FROM rows
ORDER BY scope = 'attempt', attempt_index;
