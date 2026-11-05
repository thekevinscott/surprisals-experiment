import json

from surprisals_experiment.cli.log_streams import LogStreams
from surprisals_experiment.sdk.utils.receive_event import receive_event


def test_interleaved_streams_keep_blocks_and_types_separate(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / "log.jsonl"
    monkeypatch.setenv("LABNOTES_LOG", str(path))
    streams = LogStreams()
    streams.delta("fork/0/u", "thinking", "A")
    streams.delta("fork/1/u", "text", "B")
    streams.delta("fork/0/u", "thinking", "C")
    streams.delta("fork/0/u", "text", "D")
    streams.delta("fork/1/u", "retry", "E")
    receive_event(
        {
            "type": "message_update",
            "assistantMessageEvent": {
                "type": "toolcall_delta",
                "delta": "tool arguments",
            },
        },
        on_delta=lambda kind, text: streams.delta("fork/0/ts/0", kind, text),
    )
    streams.close()
    blocks = [json.loads(line) for line in path.read_text().splitlines()]
    starts = [block for block in blocks if block["phase"] == "start"]
    assert len(starts) == 5
    contents = [
        (
            start["id"].rsplit("/", 1)[0],
            start["type"],
            "".join(
                b["content"]
                for b in blocks
                if b["id"] == start["id"] and b["phase"] == "delta"
            ),
        )
        for start in starts
    ]
    assert contents == [
        ("fork/0/u", "thinking", "AC"),
        ("fork/1/u", "text", "B"),
        ("fork/0/u", "text", "D"),
        ("fork/1/u", "retry", "E"),
        ("fork/0/ts/0", "tool", "tool arguments"),
    ]
    assert {b["id"] for b in starts} == {
        b["id"] for b in blocks if b["phase"] == "stop"
    }
    assert capsys.readouterr().out == ""


def test_without_labnotes_prints_content(monkeypatch, capsys):
    monkeypatch.delenv("LABNOTES_LOG", raising=False)
    streams = LogStreams()
    streams.delta("u", "text", "answer")
    streams.close()
    assert capsys.readouterr().out == "answer\n"
