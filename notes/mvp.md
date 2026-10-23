# MVP of Surprisals Experiment

Goal: establish and exercise a U → T → test feedback loop as the minimum first step towards plan.md. Eventually, find shorter instructions that still let T solve a problem.

# Current methodology

- U is `xiaomi/mimo-v2.6-pro`; T is `openai/gpt-oss-120b`, both accessed through OpenRouter using Pi in botbox Docker containers. U's thinking level is configurable and currently `high`.
- U receives the original APPS problem statement and writes self-contained instructions for T. Advice can be constrained by an exclusive character cap; omitting the flag leaves it uncapped.
- T receives only U's final instructions plus a fixed system prompt requiring a standard-library Python program at `/solution/main.py`. T does **not** receive the original problem, U's thinking, hidden tests, or earlier attempts.
- Each attempt uses a fresh T instance. The evaluator runs its solution against the local APPS stdin/stdout fixtures, comparing stripped output text exactly, with a five-second timeout per case.
- On failure, the persistent U session receives the aggregate number of passing tests and can inspect a read-only, pre-evaluation copy of T's source. U writes revised self-contained instructions for a fresh T. These source copies are temporary, outside the run output directory.
- Stop at the first solution that passes every stored test, or after five U/T attempts. Keep advice, transcripts, generated code, per-case results, and the final result in the run directory. U's thinking and text stream to stdout.

The previous uncapped configuration selected ten problems, once each: `0154`, `2333`, `2286`, `3784`, `3858`, `1370`, `4394`, `2229`, `2324`, and `3540`. The original `0580`, `2002`, and `3876` were removed after all three passed on their first attempt.

# Current cap experiment

The configuration now selects problem `2286` with `--u-advice-max-chars 90`. These are exclusive bounds: the whole final message, including spaces and newlines, must contain fewer characters than the configured value. Omitting the flag leaves advice uncapped.

U's system prompt is formatted with the cap and loaded once when its persistent Pi session starts. Overlong advice triggers a message stating its actual length and the bound, asking U to rewrite it. Nothing is truncated. Each T attempt permits one initial U response plus up to **10 length-rewrite retries**, configurable with `--u-advice-retries`. The allowance resets after test feedback starts a new T attempt. Exhausting it aborts the run before sending invalid advice to T. All candidates are saved to `attempts/<attempt>/advices/<i>/advice.txt` with `metadata.json` containing `rejected` and `measurement` (currently character count). They also remain in the native Pi session files in `u_transcripts/`. Rewrites do not consume T attempts.

The hypothesis is that restricting U's message will provoke useful test-feedback iterations. T still sees only U's advice, not the original problem: the budget constrains both task specification and solution guidance. Failure may therefore reflect missing essential information. At cap 100, 98-character advice passed all five local tests on the first attempt. At cap 50, all five T attempts failed all five tests. At cap 90, T passed all five tests on its third attempt after two failures, demonstrating recovery through feedback.

# Eventual methodology: shorten successful advice

This is future work, not the current MVP:

1. Start uncapped (conceptually a cap of Infinity) and obtain advice that lets T pass the tests.
2. Tell U the length of that successful advice: “Your last advice was x characters. Make it shorter; the less the better.”
3. Reject candidates whose length is equal to or greater than the preceding accepted advice, allowing up to a configurable n retries. These rejected candidates do not go to T.
4. Evaluate each shorter candidate with a fresh T against the same tests. If it passes, retain it and use its length as the next bound.
5. Continue until a shorter candidate no longer passes, or U exhausts the retries without shortening. Preserve the last successful advice and the reason for stopping.

A failed shorter candidate marks the stopping point of that search, not proof that no shorter successful advice exists. Retry counts and character budgets are separate from the current five-attempt test-feedback budget.

# Notes

- The live feedback loop has now demonstrated recovery: cap 90 passed all five local tests on T attempt three after two failed attempts. Cap 100 passed all five tests on its first attempt with 98-character advice (`20261021-005819-patient-wave/100-496e`). Cap 50 exhausted all five T attempts, each passing 0/5 (`20261021-010440-floral-tooth/50-0b29`). The queued 20- and 10-character cases were held at the user's request.
- The user then requested caps 60, 70, 80, and 90 sequentially, stopping on any success. Cap 60 (`20261021-014300-noisy-wildflower`) and cap 70 (`20261021-020958-lively-frost`) each reached two T attempts, both 0/5, before U's next response hit the proxy's 600-second idle timeout. Cap 80 (`20261021-023515-super-sun`) failed with an upstream connection reset before producing advice or reaching T. These interrupted runs did not exhaust the five-attempt budget. Cap 90 (`20261021-024204-soft-firefly`) completed successfully in 30m22s: 0/5, 0/5, then 5/5 across three T attempts. No further experiments were launched. The 30-minute monitoring timer fired during the sequence, and monitoring continued through completion.
- Cap 90's accepted advice lengths were 87, 83, and 88 characters. Before attempt three, a 90-character candidate was rejected under the exclusive bound and rewritten to 88; both candidates were preserved. This also exercised the length-retry path during a real run.
- Cap 90's first failure was formatting-only on the stored fixtures: all five sequences of numbers matched, but T printed one number per line instead of space-separated numbers. The evaluator compares stripped text exactly. Attempt two misparsed binary character rows as separate integer tokens and raised `StopIteration`. The successful advice specified both input rows and output formatting. This demonstrates feedback recovery on these fixtures, not recovery from an established algorithmic error. Earlier failures at caps 50, 60, and 70 still fail when whitespace is ignored.
- During cap 90's third T attempt, the provider stream stalled and the proxy recorded an idle timeout; T subsequently resumed and completed. The final run result is successful despite that interruption.
- An earlier cap-60 launch (`20261021-014102-orange-credit`) failed before advice because Pi did not recognize the MiMo model and borrowed incompatible token-limit metadata. U's Docker image now includes an explicit model definition with `maxTokens: 131072`, verified against OpenRouter's model listing and Pi's offline registry. Caps 100 and 50 preceded this fix; the subsequent runs use it.
- Earlier completed successes all used one attempt. U's advice may have been too good, the problems too easy, or the stored tests too weak; we have not separated these explanations.
- The original three-problem run passed every problem on its first attempt, taking roughly 3–7 minutes each.
- The latest reviewed batch, `20261020-221652-round-hat`, took about two hours. Six problems passed on the first attempt: `2333` (4/4 tests), `2286` (5/5), `3858` (36/36), `1370` (19/19), `4394` (8/8), and `2229` (6/6). None required test feedback.
- The other four did not reach T: `0154` and `3784` hit botbox's 600-second proxy idle timeout; `2324` reported an aborted U request; `3540` exited 143 after about 41 minutes while U was still thinking. These interruptions do not measure solution quality or feedback effectiveness.
- Earlier runs also failed because Docker's network address pools were exhausted. Infrastructure errors must be distinguished from failed solution tests.
- Passing means passing the available local fixtures, not demonstrated general correctness. Several tasks have only a handful of tests; for example, `2333` has four and `2286` has five. Long runtime is likewise not evidence of multiple feedback turns: `2333` took almost 34 minutes and still passed on its first attempt.
