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

**Implemented: minimize characters without enforcing a ratcheting cap.**

U is explicitly asked to produce the shortest advice possible while making every T pass every test. Each turn consists of advice, n fresh T implementations, and evaluation against the full test suite. U may explore longer or equal-length advice; all candidates are tested in uncapped mode.

The first all-pass advice establishes the baseline. A strictly shorter all-pass result updates the best result and resets the no-improvement counter. Failed tests, longer successes, and equal-length successes increment it. Before the first success, every failed turn counts. Stop after `--max-turns-without-improvement` consecutive turns (default 20), an optional total-turn limit, or interruption.

Each feedback message includes the latest advice length, per-T test results, the shortest successful length, and the no-improvement count. Prior advice and implementations remain available in U's session and mounted history. Hidden test contents remain excluded. The shortest successful result survives later failures, longer successes, and interruption.

An explicitly configured fixed cap remains available for phase 2 experiments; it never tightens automatically. The optional `experiment-ratchet.toml` pilot starts uncapped across ten problems and sets the no-improvement limit to 30. Integration tests cover the stopping rule, mixed n-of-T outcomes, longer/equal candidates, counter resets, and best-result retention. Live validation of this revised policy remains outstanding.

## Phase 5: Surprisal

**Planned: implement scoring and optimize for surprisal.**

Introduce scorer S and run a separate optimization conversation minimizing surprisal. Keep the problem, U, T, n, and search budget comparable to the character condition.

Choose S, its tokenizer and conditioning context, and whether the objective is total message surprisal or average surprisal per token. Save aggregate and per-token measurements with the scoring configuration, and provide feedback to U. Score only delivered advice, not reasoning or conversation history.

Reuse n-of-T evaluation and retention of the best qualifying candidate. Test scoring and selection with a deterministic fake scorer before using a real provider.

Finally, validate selected advice with fresh T batches and compare readability at comparable effectiveness. Full-problem baselines, the readability evaluation, and the final problem set remain to be designed. Passing tests alone cannot establish the hypothesis.
