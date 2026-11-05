"""Real CLI resume checks; explicitly invoked, excluded from CI by local_only."""

import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from curtaincall import expect

PACKAGE = Path(__file__).resolve().parents[2]
PROBLEM = '../data/APPS/test/2286'


def command(output, forks=1, samples=2):
    return [sys.executable, '-m', 'surprisals_experiment.cli.run',
            '--output', str(output), '--cap-strategy', 'characters',
            '--u-thinking', 'off', '--t-samples', str(samples),
            '--t-pool-size', '1', '--max-u-turns', '1',
            '--window-forks', str(forks), '--fork-turns', '1',
            '--window-solo-turns', '0', PROBLEM]


def wait_until(process, ready, timeout=1200):
    deadline = time.monotonic() + timeout
    while not ready():
        assert process.poll() is None, 'CLI exited before the requested stop point; see cli.log'
        assert time.monotonic() < deadline, 'Timed out waiting for the stop point'
        time.sleep(0.1)
    assert process.poll() is None, 'CLI finished before it could be interrupted'


def snapshot(output):
    paths = set()
    for name in ('advice.txt', 'metadata.json', 'generation.json', 'tests.json'):
        paths.update(output.rglob(name))
    # advice.json is complete only after scoring, not when initially created.
    paths.update(p for p in output.rglob('advice.json') if 'score' in json.loads(p.read_text()))
    for generation in output.glob('**/ts/*/generation.json'):
        paths.update(p for p in (generation.parent / 'src').rglob('*') if p.is_file())
    artifacts = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
    transcripts = {p: p.read_bytes() for p in output.rglob('messages.jsonl')}
    assert artifacts and transcripts
    return artifacts, transcripts


def check_preserved(artifacts, transcripts):
    for path, (content, mtime) in artifacts.items():
        assert path.read_bytes() == content, f'Changed completed artifact: {path}'
        assert path.stat().st_mtime_ns == mtime, f'Rewrote completed artifact: {path}'
    for path, prefix in transcripts.items():
        assert path.read_bytes().startswith(prefix), f'Transcript lost its prefix: {path}'


def check_result(output, forks, samples):
    result = json.loads((output / 'result.json').read_text())
    turns = list(output.glob('windows/*/forks/*/turns/*'))
    assert len(turns) == result['attempts']
    for window in (output / 'windows').iterdir():
        assert len(list((window / 'forks').iterdir())) == forks
        for fork in (window / 'forks').iterdir():
            assert [p.name for p in (fork / 'turns').iterdir()] == ['0']
    for turn in turns:
        assert len(list((turn / 'ts').iterdir())) == samples
        assert len(list(turn.glob('ts/*/generation.json'))) == samples
        assert len(list(turn.glob('ts/*/tests.json'))) == samples
    # Each completed U turn has one assistant reply, including across restarts.
    replies = [json.loads(line) for p in output.rglob('messages.jsonl')
               for line in p.read_text().splitlines()]
    assert sum(entry.get('role') == 'assistant' and entry.get('_complete') is not False
               for entry in replies) == len(turns)


def exercise(output, ready, signum, forks=1, samples=2):
    args = command(output, forks, samples)
    with (output.parent / 'cli.log').open('w') as log:
        process = subprocess.Popen(args, cwd=PACKAGE, stdout=log, stderr=log)
        try:
            wait_until(process, ready)
            process.send_signal(signum)
            assert process.wait(timeout=120) != 0
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=120)
        before = snapshot(output)
        resumed = subprocess.run(args, cwd=PACKAGE, stdout=log, stderr=log, timeout=2400)
        assert resumed.returncode == 0, 'Resumed CLI failed; see cli.log'
    check_preserved(*before)
    check_result(output, forks, samples)


def describe_real_cli_resume():
    def it_resumes_sigterm_during_t_sampling(tmp_path):
        output = tmp_path / 'run'

        def sampling():
            # Keep a finished sample as well as an interrupted one.
            return any((p.parent / '0/tests.json').exists() and not (p / 'tests.json').exists()
                       for p in output.glob('windows/0/forks/0/turns/0/ts/1'))

        exercise(output, sampling, signal.SIGTERM)

    def it_resumes_sigint_in_the_fork_round(tmp_path):
        output = tmp_path / 'run'

        def fork_round():
            forks = output / 'windows/0/forks'
            done = list(forks.glob('*/turns/0/ts/0/tests.json'))
            return len(done) == 1 and len(list(forks.glob('*/fork.json'))) == 2

        exercise(output, fork_round, signal.SIGINT, forks=2, samples=1)

    def it_resumes_on_a_fresh_aws_instance(tmp_path):
        """AWS_RESUME_E2E=1 uv run --frozen --with boto3 pytest ... -k aws."""
        if os.environ.get('AWS_RESUME_E2E') != '1':
            pytest.skip('Set AWS_RESUME_E2E=1 to run the paid t3.small check')
        import boto3

        config = json.loads((Path.home() / '.config/aws_runner/config.json').read_text())
        assert config['instance_type'] == 't3.small'
        ec2 = boto3.client('ec2', region_name=config['region'])
        output = tmp_path / 'run'
        filters = [{'Name': 'tag:aws-runner:dir', 'Values': [str(output)]}]

        def resources():
            instances = [i for r in ec2.describe_instances(Filters=filters)['Reservations']
                         for i in r['Instances'] if i['State']['Name'] != 'terminated']
            volumes = ec2.describe_volumes(Filters=filters)['Volumes']
            return instances, volumes

        def await_cleanup():
            deadline = time.monotonic() + 180
            while any(resources()):
                assert time.monotonic() < deadline, 'Tagged AWS resources survived cleanup'
                time.sleep(2)

        args = ['uv', 'run', '--frozen', '--project', 'packages/aws_runner',
                'aws_runner', 'run', str(output), '--',
                'uv', 'run', '--frozen', '--directory', 'surprisals_experiment',
                'python', *command(output, forks=2, samples=1)[1:]]
        process = None
        with (tmp_path / 'aws.log').open('w') as log:
            try:
                process = subprocess.Popen(args, cwd=PACKAGE.parent, stdout=log, stderr=log)
                wait_until(process, lambda: any(output.glob('windows/*/forks/*/turns/*/ts/0/tests.json')))
                instances, volumes = resources()
                assert len(instances) == len(volumes) == 1
                original_id = instances[0]['InstanceId']
                assert not (output / 'result.json').exists(), 'Run finished before stop'
                process.send_signal(signal.SIGTERM)
                assert process.wait(timeout=120) != 0
                await_cleanup()
                before = snapshot(output)
                process = subprocess.Popen(args, cwd=PACKAGE.parent, stdout=log, stderr=log)
                wait_until(process, lambda: bool(resources()[0]), timeout=180)
                replacement = resources()[0]
                assert len(replacement) == 1 and replacement[0]['InstanceId'] != original_id
                assert process.wait(timeout=2400) == 0, 'AWS resume failed; see aws.log'
                await_cleanup()
                check_preserved(*before)
                check_result(output, forks=2, samples=1)
            finally:
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=120)
                # Cleanup is restricted to this test's canonical run-directory tag.
                instances, volumes = resources()
                if instances:
                    ec2.terminate_instances(InstanceIds=[i['InstanceId'] for i in instances])
                    ec2.get_waiter('instance_terminated').wait(
                        InstanceIds=[i['InstanceId'] for i in instances],
                        WaiterConfig={'Delay': 5, 'MaxAttempts': 36})
                for volume in resources()[1]:
                    ec2.delete_volume(VolumeId=volume['VolumeId'])
                await_cleanup()


@pytest.mark.parametrize("experiment", ["forks-testing", "forks-testing-aws"])
def test_experiment_relaunch_continues_both_cells(
    tmp_path, experiment, terminal, monkeypatch
):
    """RESUME_E2E=1; AWS also needs AWS_RESUME_E2E=1. Drive launch, stop and relaunch through the TUI."""
    if os.environ.get("RESUME_E2E") != "1":
        pytest.skip("Set RESUME_E2E=1 to run paid experiment relaunch checks")
    if experiment.endswith("-aws") and os.environ.get("AWS_RESUME_E2E") != "1":
        pytest.skip("Set AWS_RESUME_E2E=1 to run the paid AWS experiment check")

    # A separate checkout keeps both labnotes and AWS shipping rooted away from real runs.
    root = tmp_path / "project"
    subprocess.run(
        ["git", "clone", "--quiet", "--shared", str(PACKAGE.parent), str(root)],
        check=True,
    )
    shutil.copy2(PACKAGE.parent / ".labnotes.toml", root / ".labnotes.toml")
    definition = Path("experiments") / experiment / "experiment.toml"
    shutil.copy2(PACKAGE.parent / definition, root / definition)
    assert (root / definition).read_bytes() == (
        PACKAGE.parent / definition
    ).read_bytes()
    for name in ("data", ".env"):
        target = root / name
        if target.is_symlink():
            target.unlink()
        if not target.exists():
            target.symlink_to((PACKAGE.parent / name).resolve())
    monkeypatch.chdir(root)
    state = tmp_path / "state"
    env = dict(os.environ, XDG_STATE_HOME=str(state), TERM="xterm-256color")
    cli = [
        "uvx",
        "--from",
        "git+https://github.com/thekevinscott/labnotes@main#subdirectory=packages/python",
        "labnotes",
        "-c",
        str(root / ".labnotes.toml"),
        "experiments",
        experiment,
    ]
    # Reuse the CLI test's cheap settings, excluding output, cap strategy and problem.
    cheap = command(tmp_path / "unused")[7:-1]
    args = [*cli, "run", "--", *cheap]
    runs = root / "experiments" / experiment / "runs"

    def folders():
        return {path.parent for path in runs.glob("*/run.json")}

    def record(folder):
        return json.loads((folder / "run.json").read_text())

    def settled():
        # Daemons drop discovery records after all runs AND teardown finish and the view leaves.
        deadline = time.monotonic() + 180
        while list(state.rglob("*.socket")):
            assert time.monotonic() < deadline, (
                "Labnotes daemon/teardown did not finish"
            )
            time.sleep(0.2)

    term = None
    active = False

    def wait_for(ready, timeout=1200):
        deadline = time.monotonic() + timeout
        while not ready():
            assert time.monotonic() < deadline, term._get_screen_text()
            time.sleep(0.1)

    try:
        for invocation in (1, 2):
            term = terminal(
                shlex.join(args),
                rows=40,
                cols=200,
                env=env,
            )
            active = True
            for cell in ("characters", "surprisal"):
                expect(term.get_by_text(cell)).to_be_visible(timeout=1200)
            if invocation == 1:

                def sampling():
                    return len(folders()) == 2 and all(
                        any(folder.glob("windows/*/forks/*/turns/*/ts/*/tests.json"))
                        and not (folder / "result.json").exists()
                        and record(folder).get("ended") is None
                        for folder in folders()
                    )

                wait_for(sampling)
                original = folders()
                assert {
                    record(folder)["params"]["cap-strategy"] for folder in original
                } == {"characters", "surprisal"}
                term.key_ctrl_c()
                expect(term.get_by_text("2 runs still going.")).to_be_visible()
                expect(term.get_by_text("Stop them")).to_be_visible()
                term.write("s")
                active = False
                wait_for(
                    lambda original=original: all(
                        record(folder).get("ended") for folder in original
                    ),
                    timeout=180,
                )
                assert all(record(folder)["ended_by"] == "stop" for folder in original)
                assert all(record(folder)["exit_code"] != 0 for folder in original)
                settled()
                active = False
                before = {folder: snapshot(folder) for folder in original}
            else:
                wait_for(
                    lambda original=original: (
                        folders() != original
                        or all(
                            len(record(folder).get("invocations", [])) == 2
                            for folder in original
                        )
                    )
                )
                assert folders() == original, "Relaunch created new run folders"
                expect(term.get_by_text("2 passed, 0 failed.")).to_be_visible(
                    timeout=2400
                )
                term.key_ctrl_c()
                active = False
                settled()
                assert folders() == original
                for folder in original:
                    run = record(folder)
                    assert len(run["invocations"]) == 2
                    assert run["exit_code"] == 0
                    assert run["invocations"][-1]["exit_code"] == 0
                    check_preserved(*before[folder])
                    check_result(folder, forks=1, samples=2)
    finally:
        if term is not None:
            (tmp_path / "labnotes-screen.txt").write_text(term._get_screen_text())
            if active and list(state.rglob("*.socket")):
                term.key_ctrl_c()
                expect(term.get_by_text("Stop them")).to_be_visible()
                term.write("s")
            settled()
