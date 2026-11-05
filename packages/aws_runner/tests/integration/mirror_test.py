from aws_runner.run import run


def test_live_mirror_precedes_completion_and_final_copy(
    cloud, transport, ticking_clock, tmp_path
):
    ec2, _, config = cloud
    execute, _, state = transport
    state["polls"] = ["", "", "7"]
    assert run(ec2, config, tmp_path / "run", ["sleep", "20"]) == 7
    calls = [call.args[0] for call in execute.call_args_list]
    copies = [
        index
        for index, args in enumerate(calls)
        if args[0] == "rsync" and args[-2].startswith("ubuntu@")
    ]
    polls = [index for index, args in enumerate(calls) if "if [ -f" in args[-1]]
    assert len(copies) == 2
    assert polls[1] < copies[0] < polls[2] < copies[1]
    assert not ec2.describe_volumes()["Volumes"]


def test_files_vanishing_during_mirror_do_not_fail_the_run(
    cloud, transport, ticking_clock, tmp_path
):
    ec2, _, config = cloud
    _, _, state = transport
    state["polls"] = ["", "", "7"]
    state["copy_code"] = 24
    assert run(ec2, config, tmp_path / "run", ["sleep", "20"]) == 7
    assert not ec2.describe_volumes()["Volumes"]
