"""Replies for the fake_llm fixture, laid out like the run folder.

Run(Window(Fork(Turn(U('advice'), T(files), ...)))): the turn at Run[w][f][n] answers for
windows/w/forks/f/turns/n, and its n-th T for ts/n. U calls take the next unanswered turn in
tree order. KILL cancels the run the first time it is reached.
"""

KILL = object()


class Node(tuple):
    def __new__(cls, *children):
        return super().__new__(cls, children)


class Run(Node):
    pass


class Window(Node):
    pass


class Fork(Node):
    pass


class Turn:
    def __init__(self, u, *ts):
        self.u = u
        self.ts = ts


class U:
    def __init__(self, text):
        self.text = text


class T:
    """Steps in order: a dict of files to write, or KILL. T finishes after the last step."""

    def __init__(self, *steps):
        self.steps = steps
