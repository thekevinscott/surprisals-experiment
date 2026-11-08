import json
from contextlib import chdir

from surprisals_experiment.cli.baseline import main


async def test_t_gets_the_question_and_result_counts_passing_samples(config, botbox_script):
    (config.problem_dir / ".env").write_text("OPENROUTER_API_KEY=test-key\n")
    botbox_script.solutions.extend(["print(int(input()) * 2)\n", "print(0)\n", "print(int(input()) * 2)\n"])
    with chdir(config.problem_dir):
        await main([
            "--problem-dir", str(config.problem_dir), "--output", str(config.output), "-T", "t",
            "--t-samples", "3", "--t-pool-size", "1", "--t-sample-timeout", "300", "--t-sample-retries", "0",
        ])
    assert [session.messages for session in botbox_script.sessions] == [["Read an integer and print its double."]] * 3
    assert [json.loads((config.t_dir(0, sample) / "attempts/0/tests.json").read_text())["all_passed"]
            for sample in range(3)] == [True, False, True]
    assert json.loads(config.result_file.read_text()) == {"samples": 3, "all_passed": 2}
