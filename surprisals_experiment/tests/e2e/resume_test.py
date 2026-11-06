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
    for generation in output.glob('**/ts/*/attempts/*/generation.json'):
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
        assert len(list(turn.glob('ts/*/attempts/*/generation.json'))) == samples
        assert len(list(turn.glob('ts/*/attempts/*/tests.json'))) == samples
    # Each completed U turn has one assistant reply, including across restarts.
    replies = [json.loads(line) for p in output.rglob('messages.jsonl')
               for line in p.read_text().splitlines()]
    assert sum(entry.get('role') == 'assistant' and entry.get('_complete') is not False
               for entry in replies) == len(turns)


def sigint_default():
    # A shell's background job inherits SIGINT ignored, and so would the CLI.
    signal.signal(signal.SIGINT, signal.SIG_DFL)


def describe_real_cli_resume():
    def it_resumes_sigint_in_the_fork_round(tmp_path):
        output = tmp_path / 'run'
        forks = output / 'windows/0/forks'

        def finished():
            return list(forks.glob('*/turns/0/ts/0/attempts/*/tests.json'))

        args = command(output, forks=2, samples=1)
        with (tmp_path / 'cli.log').open('w') as log:
            process = subprocess.Popen(args, cwd=PACKAGE, stdout=log, stderr=log, preexec_fn=sigint_default)
            try:
                wait_until(process, lambda: len(finished()) == 1 and len(list(forks.glob('*/fork.json'))) == 2)
                process.send_signal(signal.SIGINT)
                assert process.wait(timeout=120) != 0
                before = snapshot(output)
                process = subprocess.Popen(args, cwd=PACKAGE, stdout=log, stderr=log, preexec_fn=sigint_default)
                wait_until(process, lambda: len(finished()) == 2)
                process.send_signal(signal.SIGINT)
                process.wait(timeout=120)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=120)
        check_preserved(*before)


LADDER = (
    "--u-thinking off --t-samples 2 --t-pool-size 1 --window-forks 1"
    " --fork-turns 1 --window-solo-turns 0 --max-u-turns 1"
)
# RunPod scorer start over 10 minutes means something is wrong.
SETUP = 600
# About twice the measured AWS launch-to-code-running (max 161 s).
LAUNCH = 330
# Covers a U turn, measured 25 s to over 7 min; two of these fit a 30-minute cell.
ATTEMPT = 600
ATTEMPTS = "windows/*/forks/*/turns/*/ts/*/attempts/*"


@pytest.mark.parametrize("experiment", ["forks-testing", "forks-testing-aws"])
def test_experiment_relaunch_continues_both_cells(
    tmp_path, experiment, terminal
):
    """Drive launch, stop and relaunch through the TUI."""
    aws = experiment.endswith("-aws")
    # A separate checkout keeps both labnotes and AWS shipping rooted away from real runs.
    root = tmp_path / "project"
    subprocess.run(
        ["git", "clone", "--quiet", "--shared", str(PACKAGE.parent), str(root)],
        check=True,
    )
    shutil.copy2(PACKAGE.parent / ".labnotes.toml", root / ".labnotes.toml")
    run = (
        "uv run --directory surprisals_experiment python -m surprisals_experiment.cli.run"
        f" --output {{run_dir}} {LADDER} {PROBLEM}"
    )
    if aws:
        run = f"uv run --project packages/aws_runner aws_runner run {{run_dir}} -- {run}"
    (root / "experiments" / experiment).mkdir(parents=True, exist_ok=True)
    (root / "experiments" / experiment / "experiment.toml").write_text(f'''\
name = "{experiment}"
setup = "uv run --project runpod_scorer runpod-scorer up"
command = "{run}"
teardown = "uv run --project runpod_scorer runpod-scorer down"
repeats = 1
continues = true
concurrency = 2

[params]
cap-strategy = ["characters", "surprisal"]
''')
    for name in ("data", ".env"):
        target = root / name
        if target.is_symlink():
            target.unlink()
        if not target.exists():
            target.symlink_to((PACKAGE.parent / name).resolve())
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
    args = ["sh", "-c", 'cd "$0" && exec "$@"', str(root), *cli, "run"]
    runs = root / "experiments" / experiment / "runs"
    # Kevin: no run-time cap on the AWS cell beyond its infra waits.
    attempt = float("inf") if aws else ATTEMPT

    if aws:
        import boto3

        config = json.loads((Path.home() / ".config/aws_runner/config.json").read_text())
        ec2 = boto3.client("ec2", region_name=config["region"])

    def resources(folder):
        filters = [{"Name": "tag:aws-runner:dir", "Values": [str(folder.resolve())]}]
        instances = [i for r in ec2.describe_instances(Filters=filters)["Reservations"]
                     for i in r["Instances"] if i["State"]["Name"] != "terminated"]
        return instances, ec2.describe_volumes(Filters=filters)["Volumes"]

    def live(folder):
        return {i["InstanceId"] for i in resources(folder)[0]
                if i["State"]["Name"] in ("pending", "running")}

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

    scorer_users = Path.home() / ".runpod/users"
    hold = None

    def hold_scorer():
        # Keeps the pod alive through invocation 1's teardown so the relaunch finds it warm.
        nonlocal hold
        [pod] = {path.parent for path in scorer_users.glob("*/*.json")
                 if json.loads(path.read_text())["state_dir"].startswith(str(state))}
        hold = pod / f"test-{os.getpid()}.json"
        hold.with_suffix(".tmp").write_text(json.dumps({"state_dir": str(tmp_path), "pid": os.getpid()}))
        hold.with_suffix(".tmp").replace(hold)

    term = None
    active = False
    original = set()
    instances = {}

    def wait_for(reached, timeout):
        deadline = time.monotonic() + timeout
        while not (len(folders()) >= 2 and all(reached(f) for f in folders())):
            dead = [f.name for f in folders()
                    if len(record(f)["invocations"]) == invocation
                    and record(f)["ended"] and not reached(f)]
            assert not dead, f"Runs ended early: {dead}\n{term._get_screen_text()}"
            assert time.monotonic() < deadline, term._get_screen_text()
            time.sleep(1)

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
                expect(term.get_by_text(cell)).to_be_visible(timeout=SETUP)
            wait_for(
                lambda f, original=original, invocation=invocation: f not in original
                or len(record(f)["invocations"]) == invocation,
                SETUP,
            )
            if invocation == 2:
                assert folders() == original, "Relaunch created new run folders"
            if aws:
                wait_for(live, LAUNCH)
                for folder in folders():
                    [instances[folder, invocation]] = live(folder)
            if invocation == 1:
                hold_scorer()
                wait_for(lambda f: any(f.glob(ATTEMPTS)), attempt)
                original = folders()
                assert {
                    record(folder)["params"]["cap-strategy"] for folder in original
                } == {"characters", "surprisal"}
                term.key_ctrl_c()
                expect(term.get_by_text("2 runs still going.")).to_be_visible()
                expect(term.get_by_text("Stop them")).to_be_visible()
                term.write("s")
                active = False
                wait_for(lambda f: record(f)["ended"], 180)
                assert all(record(folder)["ended_by"] == "stop" for folder in original)
                assert all(record(folder)["exit_code"] != 0 for folder in original)
                settled()
                before = {folder: snapshot(folder) for folder in original}
                started = {folder: set(folder.glob(ATTEMPTS)) for folder in original}
            else:
                wait_for(lambda f, started=started: set(f.glob(ATTEMPTS)) - started[f], attempt)
                going = not all(record(folder)["ended"] for folder in original)
                term.key_ctrl_c()
                if going:
                    expect(term.get_by_text("Stop them")).to_be_visible()
                    term.write("s")
                active = False
                settled()
                assert folders() == original
                for folder in original:
                    assert len(record(folder)["invocations"]) == 2
                    check_preserved(*before[folder])
                    if aws:
                        assert instances[folder, 2] != instances[folder, 1]
                if aws:
                    deadline = time.monotonic() + 80
                    while any(any(resources(folder)) for folder in original):
                        assert time.monotonic() < deadline, "Tagged AWS resources survived cleanup"
                        time.sleep(2)
    finally:
        if term is not None:
            (tmp_path / "labnotes-screen.txt").write_text(term._get_screen_text())
            if active and list(state.rglob("*.socket")):
                term.key_ctrl_c()
                expect(term.get_by_text("Stop them")).to_be_visible()
                term.write("s")
            settled()
        if hold is not None:
            hold.unlink(missing_ok=True)
            subprocess.run(
                ["uv", "run", "--project", "runpod_scorer", "runpod-scorer", "reap"],
                cwd=root, check=True,
            )
