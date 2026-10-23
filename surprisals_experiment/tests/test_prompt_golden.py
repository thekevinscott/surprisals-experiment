"""Byte-exact prompt outputs captured from main before the Jinja refactor."""

import json
from pathlib import Path

import pytest

from surprisals_experiment.sdk.prompt_t import prompt_t
from surprisals_experiment.sdk.run_experiment.prepare_advice import prepare_advice
from surprisals_experiment.sdk.run_experiment.prepare_feedback import prepare_feedback
from surprisals_experiment.sdk.run_experiment.read_implementations import read_implementations
from surprisals_experiment.sdk.run_test_suite.results import TestResult as CaseResult, TestSuiteResult as SuiteResult
from surprisals_experiment.sdk.utils.u_session import open_u_session

GOLDEN = Path(__file__).with_name('golden_prompts')


def assert_golden(name, text):
    path = GOLDEN / name
    assert text.encode() == path.read_bytes()


def sources(snapshot):
    (snapshot / '0').mkdir(parents=True)
    (snapshot / '1/nested').mkdir(parents=True)
    (snapshot / '1/main.py').write_text('print({"answer": "é"})\n')
    (snapshot / '1/nested/helper.py').write_text('# <tag> & {{ literal }}\n')


def describe_prompt_golden():
    @pytest.mark.parametrize('mode', ['agent', 'chat'])
    async def it_preserves_the_system_prompt(config, mode):
        config.u_mode = mode
        config.t_samples = 2
        config.max_turns_without_improvement = 7
        async with open_u_session(config) as session:
            text = session.messages[0]['content'] if mode == 'chat' else session.pi_session.mounts['/u-config/u.txt'].read_text()
            assert_golden(f'system-{mode}.txt', text)

    @pytest.mark.parametrize('mode', ['agent', 'chat'])
    @pytest.mark.parametrize('best', [None, 17])
    def it_preserves_feedback(config, tmp_path, mode, best):
        config.u_mode = mode
        config.max_turns_without_improvement = 7
        snapshot = tmp_path / 'snapshot'
        sources(snapshot)
        for sample in range(2):
            (config.t_dir(3, sample) / 'src').mkdir(parents=True)
        (config.t_dir(3, 0) / 'timeouts.txt').write_text('timeout\ntimeout\n')
        (config.t_dir(3, 1) / 'src/main.py').write_text('print(1)\n')
        results = [SuiteResult([CaseResult(0, False, 'error', '', '', None)]),
                   SuiteResult([CaseResult(0, True, 'passed', '1', '', 0)])]
        text = prepare_feedback(config, 3, results, snapshot=snapshot,
                                advice_length=21, best_length=best, turns_without_improvement=2)
        assert_golden(f'feedback-{mode}-{best}.txt', text)

    @pytest.mark.parametrize('failed', [False, True])
    @pytest.mark.parametrize('missing', [False, True])
    async def it_preserves_compaction(config, botbox_script, failed, missing):
        config.u_mode = 'chat'
        config.question_file.write_text('Solve {"n": 2}.\nKeep <tags> & braces {{x}}.\n')
        botbox_script.advice.append({'status': 400} if failed else 'Remember <edge> & {cases}.\n')
        async with open_u_session(config) as session:
            session.best_advice = None if missing else 'Use {"n": 2}.\n'
            session.best_length = None if missing else 14
            session.turns_without_improvement = 3
            await session.compact()
            assert_golden(f'compacted-{failed}-{missing}.txt', session.messages[-1]['content'])
        transcript = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
        assert_golden('compact-request.txt', transcript[1]['content'])

    async def it_preserves_t_instructions_and_advice(config, botbox_script, tmp_path):
        botbox_script.solutions.append('print(1)\n')
        advice = 'Use {braces} & <tags>.\n'
        await prompt_t(config, advice, output=tmp_path / 'solution')
        assert_golden('t-system.txt', botbox_script.t_sessions[0].agent.instructions)
        assert botbox_script.t_sessions[0].messages == [advice]

    def it_preserves_implementation_headers_and_json(tmp_path):
        sources(tmp_path)
        assert_golden('implementations.txt', read_implementations(tmp_path))
        empty = tmp_path / 'empty'
        empty.mkdir()
        assert_golden('implementations-empty.txt', read_implementations(empty))

    @pytest.mark.parametrize('mode', ['agent', 'chat'])
    async def it_passes_the_original_request_through_prepare_advice(config, botbox_script, chat_provider, mode):
        config.u_mode = mode
        botbox_script.advice.append('Advice with {braces}.')
        request = 'Problem or feedback: {"x": "é"}\n<original> & literal {{x}}\n'
        async with open_u_session(config) as session:
            assert await prepare_advice(config, session, request, attempt=0) == 'Advice with {braces}.'
            sent = chat_provider[0]['messages'][-1]['content'] if mode == 'chat' else session.pi_session.messages[-1]
            assert_golden('advice-request.txt', sent)
