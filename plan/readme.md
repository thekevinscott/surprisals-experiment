# Experiment plan

Does optimizing advice for surprisal produce more understandable text than optimizing for character count, at comparable effectiveness?

U reads an APPS programming problem and writes advice. T receives that advice and writes a solution. Tests measure effectiveness; a separate readability evaluation will measure human understandability. Advice useful to another model may differ from advice useful to a human.

## Phase 1: Uncapped advice

**Complete: establish U → T → test feedback.**

U receives the problem statement without hidden tests or a reference solution. A fresh T receives only U's advice and fixed instructions for writing Python. On failure, U receives the number of passing tests and access to a read-only copy of T's source, then writes new advice for a fresh T. U retains its conversation. The run stops on success or after five attempts.

The initial three problems passed on their first attempt. A subsequent ten-problem batch produced six more first-attempt successes; four runs stopped on infrastructure errors before reaching T. These successes established the execution path but did not exercise recovery through feedback.

## Phase 2: Capped advice

**Complete: exercise both the advice-rewrite and test-feedback loops.**

Give U a fixed character cap. Advice must be strictly shorter than the cap, including whitespace. Overlong advice is saved and rejected before reaching T; U receives its measured length and is asked to rewrite. Each T attempt allows ten rewrite retries in addition to the initial candidate. Rewrites do not consume T attempts.

Preliminary results on APPS problem `2286`:

| Cap | Outcome |
| --- | --- |
| 100 | Passed all five stored tests on the first T attempt with 98-character advice. |
| 50 | Exhausted five T attempts without passing the tests. |
| 90 | Passed all five stored tests on the third T attempt. |

The cap-90 result met the goal of demonstrating the attempt loop. Recovery involved input parsing and output formatting; it does not establish an algorithmic improvement. Infrastructure failures are separate from failing solutions, and passing the stored fixtures does not establish general correctness.

Integration tests now cover both loops, including their interaction, with globally mocked Botbox sessions and real artifact writing and subprocess evaluation.

## Phase 3: n-of-T evaluation

**Complete: evaluate each advice with n independent T instances, validated locally and on Linode.**

With APPS problem `2286`, a 100-character cap, and five T samples, the local run reached 5/5 on its fifth advice attempt. The remote run exhausted five attempts, reaching 4/5 on both its fourth and fifth attempts. This validates successful qualification and budget exhaustion, not reliability across problems.

Set n with `--t-samples` (default 5; use 1 for the original single-T behavior). Freeze the advice and give the same message to n fresh T sessions. Do not revise it between evaluations or share T histories. Each solution must pass the full stored test suite; advice qualifies only when **n out of n** solutions pass.

Preserve each T's code, transcript, and test results, plus the aggregate outcome. Return all individual outcomes and source access to U after the batch. An incomplete batch caused by infrastructure errors cannot establish n/n success; the current policy is to stop on infrastructure errors, preserve completed evaluations, and leave the batch incomplete. Automatic resumption is not implemented.

Keep n separate from U's turn budget and advice-rewrite retries. Initially retain fixed-cap mode to validate this change; n=1 should preserve current behavior. Integration tests cover all-pass, mixed-pass, all-fail, and interrupted batches, identical advice, independent sessions, separate artifacts, and rewrites followed by a successful revised batch. Samples run in a configurable pool (`--t-pool-size`, default 3; use 1 for sequential evaluation). The full batch is evaluated even when an earlier sample fails its tests, and feedback retains sample order.

## Phase 4: Minimize advice without a preset cap

**Implemented: strict character ratchet. Live search validation and the final research policy remain open.**

Start uncapped and obtain advice that qualifies under n-of-T evaluation. Then ask U to make it as small as possible while preserving effectiveness. Measure each candidate and retain the shortest qualifying advice, even if later candidates fail.

A starting prompt to discuss:

> Your best successful advice was {characters} characters and passed all tests in {n} of {n} independent evaluations. Write the shortest self-contained advice you can that still lets T solve the problem. Return only the advice.

The merged implementation requires advice strictly shorter than the last successful advice. It saves and rejects equal-or-longer candidates before T runs, allowing ten rewrites per batch. Failed batches retain the bound; all-pass batches lower it and reset the failure streak. Twenty consecutive failed batches stop the run by default, with an optional total-batch limit. The best successful result is preserved through later failures and interruption.

The research policy remains open for discussion with Caleb: alternatively, tell U it is judged on shortness without enforcing a cap, and re-present all prior advice lengths and test outcomes every turn. This would allow temporary length increases. That alternative is documented locally, not implemented. Hidden test contents remain excluded from U's context.

Integration tests cover strict shortening, equal-or-longer rejection, failure-streak reset, and preservation of the best result. A live ratchet search remains to be run. The optional `experiment-ratchet.toml` pilot uses ten problems, starts uncapped and permits 30 consecutive failed batches; this is a configurable pilot, not a new default or a proven convergence criterion.

## Phase 5: Surprisal

**Planned: implement scoring and optimize for surprisal.**

Introduce scorer S and run a separate optimization conversation minimizing surprisal. Keep the problem, U, T, n, and search budget comparable to the character condition.

Choose S, its tokenizer and conditioning context, and whether the objective is total message surprisal or average surprisal per token. Save aggregate and per-token measurements with the scoring configuration, and provide feedback to U. Score only delivered advice, not reasoning or conversation history.

Reuse n-of-T evaluation and retention of the best qualifying candidate. Test scoring and selection with a deterministic fake scorer before using a real provider.

Finally, validate selected advice with fresh T batches and compare readability at comparable effectiveness. Full-problem baselines, the readability evaluation, and the final problem set remain to be designed. Passing tests alone cannot establish the hypothesis.
