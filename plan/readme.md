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

**Next: evaluate each advice with n independent T instances.**

Make n configurable, initially five as proposed. Freeze the advice and give the same message to n fresh T sessions. Do not revise it between evaluations or share T histories. Each solution must pass the full stored test suite; advice qualifies only when **n out of n** solutions pass.

Preserve each T's code, transcript, and test results, plus the aggregate outcome. Return all individual outcomes and source access to U after the batch. An incomplete batch caused by infrastructure errors cannot establish n/n success; its retry policy remains to be specified.

Keep n separate from U's turn budget and advice-rewrite retries. Initially retain fixed-cap mode to validate this change; n=1 should preserve current behavior. Add integration tests for all-pass, mixed-pass, all-fail, and interrupted batches, identical advice, independent sessions, and separate artifacts.

## Phase 4: Minimize advice without a preset cap

**Planned; search policy still open.**

Start uncapped and obtain advice that qualifies under n-of-T evaluation. Then ask U to make it as small as possible while preserving effectiveness. Measure each candidate and retain the shortest qualifying advice, even if later candidates fail.

A starting prompt to discuss:

> Your best successful advice was {characters} characters and passed all tests in {n} of {n} independent evaluations. Write the shortest self-contained advice you can that still lets T solve the problem. Return only the advice.

We still need to choose how to drive this search:

- Ask for shorter advice and evaluate candidates using length and effectiveness feedback. This permits temporary length increases while repairing failures.
- Enforce a decreasing bound based on the best qualifying advice, rejecting equal-or-longer candidates before T runs. This avoids a preset cap but still imposes a dynamic hard threshold.

Neither policy is decided. Also choose the optimization budget and whether to stop on the first failed shorter candidate, allow recovery, or stop after a period without improvement. One failed candidate does not prove further compression is impossible.

Preserve all candidates and the best qualifying advice. Add tests for shorter successes, shorter failures, equal/longer candidates, budget exhaustion, and retention of the best result.

## Phase 5: Surprisal

**Planned: implement scoring and optimize for surprisal.**

Introduce scorer S and run a separate optimization conversation minimizing surprisal. Keep the problem, U, T, n, and search budget comparable to the character condition.

Choose S, its tokenizer and conditioning context, and whether the objective is total message surprisal or average surprisal per token. Save aggregate and per-token measurements with the scoring configuration, and provide feedback to U. Score only delivered advice, not reasoning or conversation history.

Reuse n-of-T evaluation and retention of the best qualifying candidate. Test scoring and selection with a deterministic fake scorer before using a real provider.

Finally, validate selected advice with fresh T batches and compare readability at comparable effectiveness. Full-problem baselines, the readability evaluation, and the final problem set remain to be designed. Passing tests alone cannot establish the hypothesis.
