import asyncio
from contextlib import aclosing

import pytest

from state_machine import Level, StateMachine, Stop


async def events(queue):
    while True:
        yield await queue.get()


async def test_ordered_rules_and_nested_scopes():
    source = [{'id': 1, 'urgent': False}, {'id': 2, 'urgent': True}, {'id': 3, 'urgent': True}]

    async def outer(scope):
        assert scope == {}
        return source

    async def inner(scope):
        assert scope['id'] == 2
        assert [row['id'] for row in scope['rows']] == [2, 3]
        return [{'result': 'selected'}]

    machine = StateMachine('root', {
        'root': Level(outer, (('detail', lambda row: row['urgent']), ('waiting', lambda row: True)), 'done'),
        'detail': Level(inner, (), 'selected'),
    }, {'waiting': Stop, 'done': Stop, 'selected': Stop})
    state, scope = await machine.classify()
    assert state == await machine.state() == 'selected'
    assert scope == {'id': 2, 'urgent': True, 'result': 'selected', 'state': 'selected',
                     'rows': [{'result': 'selected', 'state': 'selected'}]}
    assert all('state' not in row for row in source)


async def test_actions_reclassify_before_dispatching_again():
    completed = []

    async def facts(scope):
        return [{'count': len(completed)}]

    async def work(scope):
        completed.append(scope['count'])

    machine = StateMachine('root', {
        'root': Level(facts, (('work', lambda row: row['count'] < 2),), 'done'),
    }, {'work': work, 'done': Stop})
    async with aclosing(events(asyncio.Queue())) as stream:
        result = await machine.run(stream)
    assert completed == [0, 1]
    assert result['state'] == 'done'
    assert result['count'] == 2


async def test_external_events_trigger_reclassification():
    queue = asyncio.Queue()
    started = asyncio.Event()
    ready = False
    calls = 0

    async def facts(scope):
        return [{'ready': ready}]

    async def start(scope):
        nonlocal calls
        calls += 1
        started.set()

    machine = StateMachine('root', {
        'root': Level(facts, (('done', lambda row: row['ready']),), 'start'),
    }, {'start': start, 'done': Stop})
    async with aclosing(events(queue)) as stream:
        task = asyncio.create_task(machine.run(stream))
        await started.wait()
        ready = True
        await queue.put(None)
        result = await asyncio.wait_for(task, 1)
    assert result['ready'] is True
    assert calls == 1


@pytest.mark.parametrize('cancel', [False, True])
async def test_pending_event_read_is_cancelled_on_error_or_cancellation(cancel):
    reading = asyncio.Event()
    closed = asyncio.Event()
    action_started = asyncio.Event()

    async def stream():
        try:
            reading.set()
            await asyncio.Future()
            yield None
        finally:
            closed.set()

    async def facts(scope):
        return [{}]

    async def action(scope):
        await reading.wait()
        action_started.set()
        if cancel:
            await asyncio.Future()
        raise LookupError('action failed')

    machine = StateMachine('root', {'root': Level(facts, (), 'act')}, {'act': action})
    async with aclosing(stream()) as source:
        task = asyncio.create_task(machine.run(source))
        await action_started.wait()
        if cancel:
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else LookupError):
            await task
    assert closed.is_set()


async def test_unchanged_state_retries_three_times_then_fails():
    calls = 0

    async def facts(scope):
        return [{}]

    async def action(scope):
        nonlocal calls
        calls += 1

    machine = StateMachine('root', {'root': Level(facts, (), 'act')}, {'act': action})
    async with aclosing(events(asyncio.Queue())) as stream:
        with pytest.raises(RuntimeError, match='made no progress after 3 actions'):
            await asyncio.wait_for(machine.run(stream), 10)
    assert calls == 3


async def test_empty_facts_identify_the_level():
    async def facts(scope):
        return []

    machine = StateMachine('root', {'root': Level(facts, (), 'done')}, {'done': Stop})
    with pytest.raises(ValueError, match='Level root returned no facts'):
        await machine.classify()


@pytest.mark.parametrize('actions', [{}, {'done': Stop, 'extra': Stop}])
def test_leaf_actions_must_match(actions):
    async def facts(scope):
        return [{}]

    with pytest.raises(ValueError, match='State/action mismatch'):
        StateMachine('root', {'root': Level(facts, (), 'done')}, actions)
