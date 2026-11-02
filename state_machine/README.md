# state-machine

State and actions are async, zero-argument callables. The caller owns all state logic.

```python
from state_machine import state_machine, Stop

await state_machine(
    state=read_state,
    actions={"advice_missing": write_advice, "unscored": score_advice, "done": Stop},
)
```

1. Call `state()` to read the current state name.
2. Look up its action and run it to completion, or return if it is `Stop`.
3. Repeat from step 1.

Action keys must be strings; an unknown state raises `KeyError`.
Actions must change what `state()` reads, or the same action runs again.
