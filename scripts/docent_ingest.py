"""Upload a run's U and T Pi transcripts to the Docent collection named after its experiment.

Usage: uv run --no-project --with 'docent-python>=0.1.83' scripts/docent_ingest.py runs/<experiment>/<run>
"""

import json
import sys
from pathlib import Path

from docent import Docent
from docent.data_models import AgentRun, Transcript
from docent.data_models.chat import (
    AssistantMessage,
    ContentReasoning,
    ContentText,
    ToolCall,
    ToolMessage,
    UserMessage,
    check_agent_runs,
    format_check_report,
)


def text(content):
    return "\n".join(block["text"] for block in content if block["type"] == "text")


def convert_message(message):
    role, content = message["role"], message["content"]
    if role == "user":
        return UserMessage(content=text(content))
    if role == "toolResult":
        return ToolMessage(
            content=text(content),
            tool_call_id=message["toolCallId"],
            function=message["toolName"],
            error={"message": text(content)} if message["isError"] else None,
        )
    blocks, calls = [], []
    for block in content:
        if block["type"] == "thinking":
            blocks.append(ContentReasoning(reasoning=block["thinking"]))
        elif block["type"] == "text":
            blocks.append(ContentText(text=block["text"]))
        elif block["type"] == "toolCall":
            calls.append(ToolCall(id=block["id"], function=block["name"], arguments=block["arguments"], type="function"))
    return AssistantMessage(content=blocks, model=message["model"], tool_calls=calls or None)


def transcript(directory, metadata):
    sessions = sorted(directory.rglob("*.jsonl"))
    if not sessions:
        return None
    messages = [
        convert_message(entry["message"])
        for session in sessions
        for entry in map(json.loads, session.read_text().splitlines())
        if entry["type"] == "message"
    ]
    return AgentRun(transcripts=[Transcript(messages=messages)], metadata=metadata)


def problem_runs(run):
    return [run] if (run / "settings.json").exists() else sorted(p for p in run.iterdir() if (p / "settings.json").exists())


def convert(run):
    experiment = run.parent.name
    agent_runs, missing = [], []
    for problem_run in problem_runs(run):
        record = json.loads((problem_run / "run.json").read_text())
        result_file = problem_run / "result.json"
        result = json.loads(result_file.read_text()) if result_file.exists() else {}
        base = {
            "experiment": experiment,
            "run": run.name,
            "problem_run": problem_run.relative_to(run.parent).as_posix(),
            "problem": Path(record["params"]["problem-dir"]).name,
            "exit_code": record["exit_code"],
            "settings": json.loads((problem_run / "settings.json").read_text()),
        }
        u = transcript(problem_run / "u_transcripts", base | {
            "agent": "U", "success": result.get("success"), "attempts": result.get("attempts"),
        })
        agent_runs.append(u) if u else missing.append(f"{base['problem_run']} U")
        for sample in sorted((problem_run / "attempts").glob("*/t_samples/*")):
            attempt = sample.parent.parent
            accepted = [
                json.loads(m.read_text()) for m in sorted(attempt.glob("advices/*/metadata.json"), key=lambda p: int(p.parent.name))
            ]
            accepted = [m for m in accepted if not m["rejected"]]
            tests_file = sample / "tests.json"
            tests = json.loads(tests_file.read_text()) if tests_file.exists() else None
            t = transcript(sample / "t_transcripts", base | {
                "agent": "T",
                "attempt": int(attempt.name),
                "sample": int(sample.name),
                "advice_chars": accepted[-1]["measurement"] if accepted else None,
                "tests_passed": tests and tests["passed"],
                "tests_total": tests and tests["total"],
                "scores": {"all_passed": bool(tests and tests["all_passed"])},
            })
            agent_runs.append(t) if t else missing.append(f"{base['problem_run']} T {attempt.name}/{sample.name}")
    return experiment, agent_runs, missing


def main(path):
    experiment, agent_runs, missing = convert(Path(path).resolve())
    print(f"{len(agent_runs)} agent runs; {len(missing)} without a transcript: {missing}")
    print(format_check_report(check_agent_runs(agent_runs)))
    name = f"surprisals-experiment/{experiment}"
    client = Docent()
    collection = next((c["id"] for c in client.list_collections() if c["name"] == name), None)
    collection = collection or client.create_collection(name=name, description="U and T Pi transcripts")
    print(client.add_agent_runs(collection, agent_runs))
    print(f"https://docent.transluce.org/collection/{collection}")


if __name__ == "__main__":
    main(sys.argv[1])
