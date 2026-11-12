from surprisals_experiment.cli.print_delta import PrintDelta


def test_labels_each_switch_between_streams(capsys):
    print_delta = PrintDelta()
    print_delta("fork/0/u", "thinking", "A")
    print_delta("fork/0/u", "thinking", "B")
    print_delta("fork/1/ts/0", "text", "C")
    print_delta("fork/0/u", "text", "D")
    assert capsys.readouterr().out == (
        "\n[fork/0/u thinking]\nAB\n[fork/1/ts/0 text]\nC\n[fork/0/u text]\nD"
    )
