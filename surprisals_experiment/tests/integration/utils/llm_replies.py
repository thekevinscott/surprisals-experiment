"""Replies for the fake_llm fixture, laid out like the run folder.

Run(Window(Fork(Turn(U(...), Sample(T(...), ...), ...)))): the turn at Run[w][f][n] answers for
windows/w/forks/f/turns/n, and its s-th Sample for ts/s. Each reply is used once: U calls take
the next unanswered turn in tree order; each T call on a sample takes that sample's next T.
"""


class Node(tuple):
    def __new__(cls, *children):
        return super().__new__(cls, children)


class Run(Node):
    pass


class Window(Node):
    pass


class Fork(Node):
    pass


class Sample(Node):
    pass


class Turn:
    def __init__(self, u, *samples):
        self.u = u
        self.samples = samples


class U:
    def __init__(self, text, *, thinking):
        self.text = text
        self.thinking = thinking


class T:
    """T thinks, writes its files, then says its text."""

    def __init__(self, files, *, thinking, text):
        self.files = files
        self.thinking = thinking
        self.text = text
