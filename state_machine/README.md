# state-machine

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

## Testing

`state_machine.testing` runs a machine against a world and checks the files it leaves on disk.
A world is a list of `State`s in call order, each a reply to one request and the logs and files expected right after it, ending in `Done` unless the run is killed.
Expected `files` hold only what changed since the previous state.
Contents are str (text), bytes, dict (JSON) or list (JSON lines); `REMOVED` marks a deleted path; `...` at any depth means "present, not checked".
Subclass `FakeWorld` to fake what the run calls, answering each call with `answer` and `delivered`; `execute(fake, run)` drives the run and checks every state and the end.
