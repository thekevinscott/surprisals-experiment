import json

from aws_runner.run import run


def test_ships_working_tree_env_and_provenance(cloud, transport, tmp_path):
    ec2, _, config = cloud
    execute, _, _ = transport
    directory = tmp_path / "cell with spaces"
    assert run(ec2, config, directory, ["uv", "run", "experiment.py"]) == 0
    assert json.loads((directory / "aws_runner.json").read_text()) == {
        "commit": "abc123",
        "dirty": True,
    }
    calls = execute.call_args_list
    upload = next(call.args[0] for call in calls if call.args[0][-1].endswith("/repo/"))
    assert "--exclude=.git" in upload
    assert not any(".env" in arg for arg in upload)
    script = next(
        call.kwargs["input"]
        for call in calls
        if call.args[0][-1].endswith("/command.sh")
    )
    assert "cd /srv/aws-runner/repo" in script
    assert "uv run experiment.py" in script
    assert "export PATH=/home/ubuntu/.local/bin:$PATH" in script
    assert any(
        "ln -s /srv/aws-runner/run" in call.kwargs.get("input", "") for call in calls
    )
