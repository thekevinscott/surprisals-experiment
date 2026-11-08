"""Upload a run's U and T Pi transcripts to the Docent collection named after its experiment.

Usage: uv run --project scripts/docent-upload docent-upload experiments/<experiment>/runs/<run>
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
    SystemMessage,
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
    if role == "system":
        return SystemMessage(content="\n\n".join(message["sections"].values()))
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


def transcript(directories, metadata):
    sessions = next((found for d in directories if (found := sorted(d.rglob("*.jsonl")))), [])
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
        # Runs before botbox 0.1.70 used u_transcripts/ and t_transcripts/.
        u = transcript([problem_run / "u/transcripts", problem_run / "u_transcripts"], base | {
            "agent": "U", "success": result.get("success"), "attempts": result.get("attempts"),
        })
        agent_runs.append(u) if u else missing.append(f"{base['problem_run']} U")
        for try_ in sorted(problem_run.glob("windows/*/forks/*/turns/*/ts/*/attempts/*")):
            sample = try_.parent.parent
            attempt = sample.parent.parent
            metadata_file = attempt / "metadata.json"
            metadata = json.loads(metadata_file.read_text()) if metadata_file.exists() else None
            advice = json.loads((problem_run / metadata["advice"] / "advice.json").read_text()) if metadata else None
            tests_file = try_ / "tests.json"
            tests = json.loads(tests_file.read_text()) if tests_file.exists() else None
            t = transcript([try_ / "transcripts"], base | {
                "agent": "T",
                "attempt": int(attempt.name),
                "sample": int(sample.name),
                "t_attempt": int(try_.name),
                "advice_chars": advice["score"] if advice else None,
                "tests_passed": tests and tests["passed"],
                "tests_total": tests and tests["total"],
                "scores": {"all_passed": bool(tests and tests["all_passed"])},
            })
            agent_runs.append(t) if t else missing.append(f"{base['problem_run']} T {attempt.name}/{sample.name}/{try_.name}")
    return experiment, agent_runs, missing


def main():
    experiment, agent_runs, missing = convert(Path(sys.argv[1]).resolve())
    print(f"{len(agent_runs)} agent runs; {len(missing)} without a transcript: {missing}")
    print(format_check_report(check_agent_runs(agent_runs)))
    name = f"surprisals-experiment/{experiment}"
    client = Docent()
    collection = next((c["id"] for c in client.list_collections() if c["name"] == name), None)
    collection = collection or client.create_collection(name=name, description="U and T Pi transcripts")
    print(client.add_agent_runs(collection, agent_runs))
    print(f"https://docent.transluce.org/collection/{collection}")
