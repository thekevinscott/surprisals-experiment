# Python Problems Experiment

https://docs.google.com/document/d/1ejmE9Nm-pD1eeeQj393WRSIkUoEvIStnPvlYjJcCR1o/edit?tab=t.0#heading=h.2n8xdqnaoemr

## Research question

Does optimizing instructions for surprisal produce more understandable text than optimizing for characters, at comparable effectiveness?

We want to compare two ways of bottlenecking the information U communicates to T. In this experiment, U communicates **what the problem is**, rather than a strategy for solving a problem T already knows.

Successful code execution establishes effectiveness. A separate readability evaluation is needed to test the hypothesis about understandability.

## Dataset and models

Use [APPS](https://github.com/hendrycks/apps) rather than MBPP, following Caleb's recommendation: its problems are more substantial and its descriptions specify the requirements without relying on access to test cases.

- **U:** Writes and iteratively compresses the problem description.
- **T:** Receives U's message and generates a solution. Use a reasonably capable model that can solve the problems when given their full descriptions.
- **S:** Scores the surprisal of U's message. Model and scoring context remain to be chosen.

U receives the original problem description, but no test cases. T receives problem information only through U's message, alongside fixed generic instructions for producing code. The evaluator keeps the test cases separate from both models.

Whether U receives a reference solution remains open; the initial proposal is to give it only the problem description.

## Implementation roadmap

The immediate sequence is: **n independent T evaluations per advice → character minimization without a preset cap → surprisal minimization**. These are planned changes, not implemented behavior.

### Current checkpoint

The MVP runs one fresh T per advice candidate. Fixed character caps exercised both the advice-rewrite loop and the U → T → test-feedback loop. The cap-90 run passed on its third T attempt, meeting the immediate goal of demonstrating feedback recovery. Its failures involved parsing and output formatting; it does not establish robust effectiveness or an algorithmic improvement.

Integration tests now exercise both loops and their interaction with globally mocked Botbox sessions, real artifact persistence, and real subprocess evaluation. They cover rejection, retry exhaustion, fresh T sessions, feedback, stopping, and infrastructure errors.

### 1. Evaluate each advice with n instances of T

This is already part of the proposal: evaluate the **same advice** repeatedly, with five independent T instances suggested initially. Make n configurable; n is distinct from the number of U optimization turns and advice-rewrite retries.

- Freeze the candidate advice, then give it to n fresh T sessions. Do not revise it between those evaluations or share T histories.
- Evaluate every generated solution against the same full stored test suite. A candidate qualifies only if **n out of n** solutions pass every test.
- Preserve each T's code, transcript, and test results under its candidate, with an aggregate outcome. Return the individual outcomes and source access to U after the batch completes.
- Distinguish infrastructure errors from completed but failing solutions. An incomplete batch cannot establish n/n success; retry behavior for interrupted evaluations must be specified.
- Initially retain the existing fixed-cap mode to validate this change before adding optimization. With n=1, behavior should match the current loop.

Extend the integration tests with all-pass, mixed-pass, all-fail, and infrastructure-interrupted batches. Verify that all n sessions receive identical advice, are independent, and produce separate artifacts; one passing T must not end a batch early.

### 2. Minimize characters without a preset hard cap

Start uncapped and find advice that qualifies under the n/n criterion. Then ask U to make it as small as possible while preserving effectiveness. The goal is to discover a useful message length, rather than selecting a fixed cap such as 50 or 90 in advance.

A starting prompt to discuss:

> Your best successful advice was {characters} characters and passed all tests in {n} of {n} independent evaluations. Write the shortest self-contained advice you can that still lets T solve the problem. Return only the advice.

Record the measured character count, evaluate candidates with the n-of-T batch, and retain the shortest qualifying advice found. Failed candidates must not replace that incumbent. Keep U's optimization history and all candidates, including failures.

**The search policy is still open.** Two possibilities:

- Ask for shorter advice, evaluate each candidate, and use measured length plus effectiveness feedback to guide a bounded optimization conversation. This allows temporary length increases while repairing an unsuccessful candidate.
- Enforce an adaptive bound derived from the best qualifying advice: reject equal-or-longer candidates and request rewrites before running T. This has no preset cap, but still imposes a hard, dynamically decreasing acceptance threshold.

We have not chosen between these policies. In particular, do not silently equate “try to make it as small as possible” with mandatory strict shortening on every response. Also decide whether to stop after the first failed shorter candidate, allow recovery attempts, or use a fixed turn budget with a no-improvement stopping rule. The original proposal favors a bounded search retaining the best qualifying candidate; one failed candidate is not proof that further compression is impossible.

Before implementation, settle the prompt, candidate acceptance rule, optimization budget, and stopping rule. Then test incumbent preservation, shorter successful advice, shorter unsuccessful advice, equal/longer advice, and budget exhaustion using scripted sessions.

### 3. Implement surprisal scoring and optimization

Once the n-of-T evaluation and character search work, introduce scorer S and run a separate optimization conversation minimizing surprisal. Keep the problem, U, T, n, and search budget comparable across conditions.

Choose S, its tokenizer and conditioning prompt, and whether the objective is total message surprisal or mean surprisal per token. These are substantive experimental choices, not interchangeable measurements. Preserve the scoring configuration, aggregate score, and per-token scores; provide the chosen feedback to U. Only the delivered advice is scored, not U's reasoning or conversation history.

Reuse candidate evaluation and retention, substituting the chosen surprisal objective for character count. Test score handling and candidate selection with a deterministic fake scorer before calling a real scoring provider.

Afterward, validate selected messages with fresh T batches and compare their readability at comparable effectiveness. Advice useful to an AI may differ from advice understandable to a human; this distinction is part of the research question.

## Target methodology

For each problem, run two separate optimization conversations: one minimizing characters and one minimizing surprisal. Use the same U, T, problem, and number of optimization turns in both conditions.

1. Give U the problem description and explain the objective and feedback format.
2. U reasons about the problem and outputs a candidate message for T. Only the candidate message is delivered to T and measured for length or surprisal.
3. Give that same message to n fresh, independent instances of T (initially five). Each generates code without seeing previous candidates or attempts.
4. Run each solution against the problem's tests. A candidate qualifies when all n solutions pass the full test suite.
5. Return T's n outputs, their individual pass/fail results, and the candidate's character count or per-token surprisal to U. Do not include hidden test inputs, expected outputs, or test-revealing error details in feedback.
6. Repeat for a fixed **N optimization turns**, asking U to reduce message cost while retaining an n/n passing rate.

Retain the lowest-cost qualifying candidate found in each conversation, not necessarily the final candidate. Record failures to find a qualifying candidate rather than silently replacing them. This finds the best message within a fixed search budget, not a proven minimum.

Caleb recommends per-token surprisal feedback. We still need to confirm whether the optimization target is **total message surprisal** or **average surprisal per token**, and what context S sees.

## Initial pilot

The proposal recommends a small, fixed set of APPS problems and a simple API chat loop. The current MVP instead uses persistent Pi/botbox agents, implemented before that feedback; the roadmap above builds on the existing implementation.

Try a few candidate Us (for example, Sonnet, Opus, GPT, and GLM) and compare their ability to produce and compress valid instructions, along with their cost. Caleb suggested choosing an effective U that is reasonably economical, roughly under $0.10 per problem; clarify whether this covers the whole optimization run and which model calls it includes.

Use the pilot to choose U, T, S, N, and the scoring configuration before scaling up. Save candidate messages, feedback, test outcomes, model settings, and costs so the optimization can be inspected and reproduced.

## Final comparison

For each problem, compare the optimized character-based and surprisal-based messages at comparable effectiveness. Confirm selected messages' effectiveness using fresh T attempts, separate from the attempts used during optimization.

Measure T's performance with the original full problem descriptions. For the final experiment, consider selecting problems T can solve under that condition, so failures primarily reflect communication difficulty. Caleb suggested deferring this filtering for the pilot.

The readability evaluation is still to be designed. Passing tests alone does not establish that a human or trusted model understands the message. Keep the comparison paired by problem, and report how often either condition fails to produce qualifying instructions.

## Open questions

- Which APPS problems, and how many, should we use for the pilot and final experiment?
- Which U, T, and S should we use? Should S equal T?
- What context should S receive: U's context, no context, or a fixed scoring prompt?
- Does "per-token surprisal" refer to feedback, the optimization objective, or both?
- How many optimization turns should U receive? What is the cost budget?
- Does U receive reference solutions, or only problem descriptions?
- What fixed code-output instructions or interface scaffolding does T need?
- How many fresh attempts should validate the selected messages?
- How will we evaluate readability or understandability?
