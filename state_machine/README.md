State and actions are async callables. Every positional argument after `actions` is passed to both. The caller owns all state logic.

```python
from state_machine import state_machine, Stop

actions = {"advice_missing": write_advice, "unscored": score_advice, "done": Stop}
await state_machine(read_state, actions, turn)
```

1. Call `state(*args)` to read the current state name.
2. Look up its action and run it with the same arguments to completion, or return if it is `Stop`.
3. Repeat from step 1.

An unknown state raises `KeyError`.
Actions must change what `state(*args)` reads, or the same action runs again.
