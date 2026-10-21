-- Run from one experiment run folder, not a batch containing multiple runs.
WITH
candidates AS (
    SELECT substr(path, 1, instr(path, '/advices/') - 1) AS attempt_path,
           content ->> 'rejected' AS rejected,
           content ->> 'measurement' AS measurement
    FROM './attempts/*/advices/*/metadata.json'
),
advice AS (
    SELECT attempt_path, count(*) AS candidates,
           count(*) - 1 AS rewrites,
           sum(rejected = 1) AS rejected_candidates,
           max(CASE WHEN rejected = 0 THEN measurement END) AS accepted_characters
    FROM candidates
    GROUP BY attempt_path
),
evaluations AS (
    SELECT substr(path, 1, length(path) - length('/tests.json')) AS attempt_path,
           content ->> 'passed' AS tests_passed,
           content ->> 'total' AS tests_total,
           content ->> 'all_passed' AS all_passed
    FROM './attempts/*/tests.json'
),
paths AS (
    SELECT attempt_path FROM advice
    UNION SELECT attempt_path FROM evaluations
),
attempts AS (
    SELECT cast(substr(p.attempt_path, instr(p.attempt_path, 'attempts/') + 9) AS integer) AS attempt_index,
           a.candidates AS advice_candidates,
           a.rewrites AS advice_rewrites,
           a.rejected_candidates,
           a.accepted_characters,
           e.tests_passed, e.tests_total,
           CASE WHEN e.attempt_path IS NULL THEN 0 ELSE 1 END AS completed_t_evaluations,
           e.all_passed AS passing_ts,
           CASE WHEN e.all_passed = 1 THEN 'passed'
                WHEN e.all_passed = 0 THEN 'failed_tests'
                ELSE 'not_evaluated' END AS outcome
    FROM paths p
    LEFT JOIN advice a USING (attempt_path)
    LEFT JOIN evaluations e USING (attempt_path)
),
run_metadata AS (
    SELECT content FROM './run.json'
),
result AS (
    SELECT content FROM './result.json'
),
rows AS (
    SELECT 'run' AS scope, NULL AS attempt_index,
           sum(advice_candidates) AS advice_candidates,
           sum(advice_rewrites) AS advice_rewrites,
           sum(rejected_candidates) AS rejected_candidates,
           NULL AS accepted_characters,
           coalesce(sum(completed_t_evaluations), 0) AS completed_t_evaluations,
           coalesce(sum(passing_ts), 0) AS passing_ts,
           NULL AS tests_passed, NULL AS tests_total,
           CASE (SELECT content ->> 'success' FROM result)
               WHEN 1 THEN 'passed' WHEN 0 THEN 'failed_tests'
               ELSE 'no_final_result' END AS outcome
    FROM attempts
    UNION ALL
    SELECT 'attempt', attempt_index, advice_candidates, advice_rewrites,
           rejected_candidates, accepted_characters, completed_t_evaluations,
           passing_ts, tests_passed, tests_total, outcome
    FROM attempts
)
SELECT
    (SELECT content ->> '$.params."u-advice-max-chars"' FROM run_metadata) AS cap,
    CASE WHEN EXISTS (
        SELECT 1 FROM run_metadata, json_each(content, '$.params')
        WHERE key = 'u-advice-max-chars'
    ) THEN 'recorded' ELSE 'unknown' END AS cap_status,
    1 AS ts_per_advice,
    CASE WHEN EXISTS (SELECT 1 FROM evaluations WHERE all_passed = 1)
         THEN (SELECT count(*) FROM attempts WHERE completed_t_evaluations = 1
               AND attempt_index <= (SELECT min(attempt_index) FROM attempts WHERE passing_ts = 1))
         END AS evaluation_attempts_to_success,
    rows.*
FROM rows
ORDER BY CASE scope WHEN 'run' THEN 0 ELSE 1 END, attempt_index;
