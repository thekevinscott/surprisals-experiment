# Read-through: run 20261022-214114-empty-waterfall (APPS 0154)

Run: runs/advice-convergence/20261022-214114-empty-waterfall/ (878 files).
Questions: Fable. Data pulls: 4 Sonnet agents (curve, advice, U, T). Spot-checked: stop 3 of 3, best 192 chars.

## Facts
- 38 attempts, 72 min, success. Advice 2325 -> 192 chars (attempt 34), ratio 0.083.
- Stop rule was 3, not 30. The value is not recorded in settings.json or run.json; only feedback.txt shows it ("3 of 3").
- Cap was off; the prompt said "fewer than Infinity characters". U never reacted to it.
- 28 of 38 attempts were 5/5. 10 were mixed (9 at 4/5, one at 3/5), at every length from 935 down.
- 11 failing samples: 6 IndentationError (stray space copying code), 4 wrote no main.py, 1 wrong answer (attempt 19, T ignored the formula).
- U solved the problem analytically in turn 1 (closed form, 11.7 min of thinking). Later turns 15-40 s.
- U read /solutions only after failures, and correctly diagnosed T copy errors.

## What it means
- The advice became the solution. From about attempt 12 it is formula plus code to copy; from 15 it is pure dictation. 3 of 5 T outputs at attempt 34 are byte-identical to the advice code.
- Real compression ended near 250 chars (attempt 22). After that the code is fixed and gains come from stripping spaces and swapping words for symbols (→ ⇒ ∈). U miscounted chars with these symbols.
- The minimum is set by T noise, not advice quality. Near-identical advice passed one turn and failed the next (29/30/31, 34/35/36). About 1 in 4 attempts fails all-5 by chance, so the recorded best is the luckiest draw.
- It stopped on the rule, not a plateau: U was still shaving 1-2 chars per turn.

## Implications for the 20-problem batch (stop 30)
- Curves will likely be geometric then a long sawtooth tail of cosmetic cuts. "Levels out" will mostly measure T formatting noise times patience.
- With stop 30, more turns means more lucky draws, so best length keeps creeping down slowly. Expect a tail, not a clean plateau.
- Cost: about 95 s per turn; ~1 h+ per problem; 20 problems at concurrency 3 is roughly 7 h, longer if stop 30 adds turns.
- Record max_turns_without_improvement and stop reason in settings.json/result.json; today they must be inferred.

## Candidate targeted experiments (each answers one question)
1. Noise floor: rerun T many times on fixed advice (attempt 0's 2325 chars and attempt 34's 192 chars). Question: what is the per-sample failure rate, and does code-in-advice raise it? Needs a fixed-advice mode; unverified whether the code has one.
2. Problems where U cannot write a closed-form answer. Question: does the curve still collapse to dictation when the solution is long code? The 20-problem batch may answer this already.

## Curve (per attempt)
chars = advice length; kpass = samples passing all 84 tests, of 5; best = best all-pass so far; tw = turns without improvement.

| att | chars | kpass | best | tw |
|---|---|---|---|---|
| 0 | 2325 | 5 | 2325 | 0 |
| 1 | 1805 | 5 | 1805 | 0 |
| 2 | 1460 | 5 | 1460 | 0 |
| 3 | 1136 | 5 | 1136 | 0 |
| 4 | 974 | 5 | 974 | 0 |
| 5 | 887 | 4 | 974 | 1 |
| 6 | 935 | 4 | 974 | 2 |
| 7 | 797 | 5 | 797 | 0 |
| 8 | 690 | 5 | 690 | 0 |
| 9 | 591 | 5 | 591 | 0 |
| 10 | 532 | 5 | 532 | 0 |
| 11 | 444 | 5 | 444 | 0 |
| 12 | 376 | 5 | 376 | 0 |
| 13 | 329 | 4 | 376 | 1 |
| 14 | 337 | 5 | 337 | 0 |
| 15 | 317 | 5 | 317 | 0 |
| 16 | 301 | 4 | 317 | 1 |
| 17 | 304 | 5 | 304 | 0 |
| 18 | 287 | 5 | 287 | 0 |
| 19 | 241 | 4 | 287 | 1 |
| 20 | 271 | 5 | 271 | 0 |
| 21 | 259 | 5 | 259 | 0 |
| 22 | 250 | 5 | 250 | 0 |
| 23 | 241 | 5 | 241 | 0 |
| 24 | 230 | 4 | 241 | 1 |
| 25 | 235 | 5 | 235 | 0 |
| 26 | 229 | 5 | 229 | 0 |
| 27 | 222 | 5 | 222 | 0 |
| 28 | 218 | 5 | 218 | 0 |
| 29 | 212 | 5 | 212 | 0 |
| 30 | 206 | 3 | 212 | 1 |
| 31 | 211 | 5 | 211 | 0 |
| 32 | 210 | 4 | 211 | 1 |
| 33 | 194 | 5 | 194 | 0 |
| 34 | 192 | 5 | 192 | 0 |
| 35 | 191 | 4 | 192 | 1 |
| 36 | 190 | 4 | 192 | 2 |
| 37 | 195 | 5 | 192 | 3 |

## Shortest all-pass advice (attempt 34, 192 chars)
    n→# of perfectly balanced striped BSTs. p=(2^h-1)//3⇒1 iff n+1-2^h∈{p,p+1} copy exactly→main.py

    ```python
    n=int(input())
    h=(n+1).bit_length()-1
    p=(2**h-1)//3
    print(+(n+1-2**h in (p,p+1)))
    ```

## Time split
U first turn 11.7 min (16%), T generation 31.7 min (44%), testing 6.0 min (8%), U later turns 22.2 min (31%). One slow T sample sets an attempt's generation time (attempt 5: 239 s vs median 37 s).

Scripts: curve_ew.py, an_waterfall.py (in this folder).
