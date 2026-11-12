class PrintDelta:
    def __init__(self):
        self.section = None

    def __call__(self, stream: str, kind: str, text: str) -> None:
        if (stream, kind) != self.section:
            print(f"\n[{stream} {kind}]", flush=True)
            self.section = (stream, kind)
        print(text, end="", flush=True)
