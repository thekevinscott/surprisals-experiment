import subprocess

from aws_runner.run import run


def test_live_mirror_precedes_completion_and_final_copy(
    cloud, transport, ticking_clock, tmp_path
):
    ec2, _, config = cloud
    execute, _ = transport
    empty = subprocess.CompletedProcess([], 0, stdout="")
    execute.side_effect = [empty] * 4 + [
        empty,
        empty,
        empty,
        subprocess.CompletedProcess([], 0, stdout="7"),
        empty,
    ]
    assert run(ec2, config, tmp_path / "run", ["sleep", "20"]) == 7
    calls = [call.args[0] for call in execute.call_args_list]
    copies = [index for index, args in enumerate(calls) if args[0] == "rsync"]
    polls = [index for index, args in enumerate(calls) if "if [ -f" in args[-1]]
    assert len(copies) == 2
    assert polls[1] < copies[0] < polls[2] < copies[1]
    assert not ec2.describe_volumes()["Volumes"]
