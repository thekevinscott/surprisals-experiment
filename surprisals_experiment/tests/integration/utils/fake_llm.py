"""Fakes U and T from a world (see state_machine/README.md), pausing the run after each reply to check its state."""

import asyncio
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import httpx2
from botbox import RunResult
from openai import AsyncOpenAI

import surprisals_experiment
from state_machine.testing import FakeWorld, masked
from surprisals_experiment.sdk.run_test_suite.run_case import run_case

from utils.world import U, Case, Score, T


class FakeLLM(FakeWorld):
    def __init__(self, world, output):
        super().__init__(world, output)
        self.boxes = []
        self.followers = {}

    def __enter__(self):
        self.patches = [
            patch('surprisals_experiment.sdk.utils.botbox_run.botbox_run.Botbox', self.botbox),
            patch('surprisals_experiment.sdk.utils.botbox_run.botbox_run.follow', self.follow),
            patch('surprisals_experiment.sdk.run_test_suite.run_test_suite_for_t.run_case', self.run_case),
            patch('surprisals_experiment.sdk.utils.u_chat.opener.AsyncOpenAI', self.openai),
            patch('measure_surprisal.utils.client.AsyncOpenAI', self.scorer),
        ]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *args):
        for p in self.patches:
            p.stop()

    def relative(self, path):
        return Path(path).relative_to(self.output).as_posix()

    async def follow(self, path, on_event):
        self.followers[path] = on_event
        await asyncio.Future()

    def say(self, stdout, kind, delta):
        """Append one pi stdout event, as T's container writes it, and hand it to follow()."""
        event = {'type': 'message_update', 'assistantMessageEvent': {'type': kind, 'delta': delta}}
        with stdout.open('a') as file:
            file.write(json.dumps(event) + '\n')
        self.followers[stdout](event)

    def openai(self, **kwargs):
        async def respond(request):
            body = json.loads(request.content)
            index, reply = await self.answer(U, body)
            if reply.error:
                await self.delivered(index)
                raise reply.error
            if reply.status != 200:
                await self.delivered(index)
                return httpx2.Response(reply.status, json={'error': {'message': 'provider failed'}})
            deltas = [{key: value} for key, value in (('reasoning', reply.thinking), ('content', reply.text))
                      if value is not None] or [{}]
            chunks = [{'id': 'u', 'object': 'chat.completion.chunk', 'created': 1, 'model': body['model'],
                       'choices': [{'index': 0, 'delta': {'role': 'assistant', **delta}, 'finish_reason': None}]}
                      for delta in deltas]
            chunks[-1]['choices'][0] |= {'finish_reason': reply.finish, **reply.choice}
            if reply.usage:
                chunks.append({'id': 'u', 'object': 'chat.completion.chunk', 'created': 1, 'model': body['model'],
                               'choices': [], 'usage': reply.usage})

            async def stream():
                for chunk in chunks:
                    yield f'data: {json.dumps(chunk)}\n\n'.encode()
                await self.delivered(index)
                if reply.drop:
                    raise httpx2.RemoteProtocolError('stream disconnected')
                yield b'data: [DONE]\n\n'

            return httpx2.Response(200, headers={'content-type': 'text/event-stream'}, content=stream())

        return AsyncOpenAI(**kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)))

    async def run_case(self, index, stdin, expected, solution_dir, timeout_seconds):
        # Blocking, on its own loop: under looptime, awaiting a real subprocess jumps virtual time to the case timeout.
        with ThreadPoolExecutor(1) as pool:
            result = pool.submit(asyncio.run, run_case(index, stdin, expected, solution_dir, timeout_seconds)).result()
        sent = (Path(solution_dir).parent.relative_to(self.output).as_posix(), index)
        turn = next((position for position in range(self.asked, len(self.states))
                     if isinstance(self.states[position].reply, Case)
                     and masked(self.states[position].sent, sent) == self.states[position].sent), None)
        if index == 0 and (turn is not None or self.done is None and self.asked >= len(self.states)):
            if turn:
                await self.arrived[turn - 1]
            state, _ = await self.answer(Case, sent)
            await self.delivered(state)
        return result

    def scorer(self, **kwargs):
        async def respond(request):
            body = json.loads(request.content)
            index, reply = await self.answer(Score, body['prompt'])
            await self.delivered(index)
            if reply.status != 200:
                return httpx2.Response(reply.status, json={'error': {'message': reply.message}})
            tokens, bits = zip(*reply.bits)
            offsets = [sum(map(len, tokens[:position])) for position in range(len(tokens))]
            return httpx2.Response(200, headers={'content-type': 'application/json'}, content=json.dumps({
                'id': 'score', 'object': 'text_completion', 'created': 1, 'model': body['model'],
                'choices': [{'index': 0, 'text': '', 'finish_reason': 'stop', 'logprobs': {
                    'tokens': tokens, 'token_logprobs': [-value * math.log(2) for value in bits],
                    'text_offset': offsets}}],
            }))

        return AsyncOpenAI(**kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)))

    @property
    def botbox(self):
        llm = self

        class Botbox:
            def __init__(self, agent, *, dockerfile):
                self.sent = {
                    'agent': {'provider': agent.provider, 'model': agent.model, 'api_key': agent.api_key},
                    'dockerfile': Path(dockerfile).relative_to(Path(surprisals_experiment.__file__).parent).as_posix(),
                }

            async def __aenter__(self):
                self.exited = False
                llm.boxes.append(self)
                return self

            async def __aexit__(self, *args):
                self.exited = True

            async def build(self):
                state = llm.states[llm.asked] if llm.asked < len(llm.states) else None
                if state and isinstance(state.reply, T) and state.reply.build_error:
                    index, t = await llm.checked(llm.ask, T, self.sent)
                    await llm.delivered(index)
                    raise t.build_error
                return 'fake'

            async def run(self, command, *, mounts, workdir, output):
                mounted = {target: Path(source) for source, target, _ in mounts}
                index, t = await llm.answer(T, {**self.sent, 'command': command, 'mounts': {
                    target: (llm.relative(source) if Path(source).is_relative_to(llm.output)
                             else {file.name: file.read_text() for file in Path(source).iterdir()}, mode)
                    for source, target, mode in mounts}, 'workdir': workdir, 'output': llm.relative(output)})
                await asyncio.sleep(t.seconds)
                stdout = Path(output) / 'stdout.txt'
                stdout.parent.mkdir(parents=True, exist_ok=True)
                if t.thinking is not None:
                    llm.say(stdout, 'thinking_delta', t.thinking)
                for name, content in t.files.items():
                    path = mounted['/solution'] / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(content, Path):
                        path.symlink_to(content)
                    elif isinstance(content, bytes):
                        path.write_bytes(content)
                    else:
                        path.write_text(content)
                if t.text is not None:
                    llm.say(stdout, 'text_delta', t.text)
                await llm.delivered(index)
                if t.error:
                    raise t.error
                if t.hang:
                    await asyncio.Future()
                return RunResult(exit_code=t.exit_code)

        return Botbox
