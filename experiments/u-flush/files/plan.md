# Plan

12 runs: 6 per strategy, to see the efficacy of each.

- Conversation U (`u-flush 0`): U keeps its conversation, as today.
- Flush U (`u-flush 1`): U is cleared every turn and sees every previous advice, each with its length and test results. If that exceeds 400,000 characters, the oldest failing advices are dropped first, then the oldest passing ones.

Efficacy per run: shortest passing advice, attempts and wall time to reach it, whether it passed at all.

- 6 vs 6 shows a large difference. Heavy overlap means the difference is small or noisy, not absent. Pilot data, so directional.
- Runs cut off by the output limit (#61) never reach the stop rule. Count them separately, or fix #61 first.
- Everything but `u-flush` is held fixed: problem 2286, chat U, same models, stop rule 50.
