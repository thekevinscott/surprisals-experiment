import subprocess


def respond(state, args, **kwargs):
    if args[:3] == ["git", "rev-parse", "--show-toplevel"]:
        output = state["checkout"]
    elif args[:3] == ["git", "rev-parse", "HEAD"]:
        output = "abc123\n"
    elif args[:3] == ["git", "status", "--porcelain"]:
        output = " M experiment.py\n"
    elif args[0] == "ssh" and "if [ -f" in args[-1]:
        output = state["polls"].pop(0) if len(state["polls"]) > 1 else state["polls"][0]
    else:
        output = ""
    if args[0] == "rsync" and args[-2].startswith("ubuntu@") and state["fail_copy"]:
        raise subprocess.CalledProcessError(23, args)
    return subprocess.CompletedProcess(args, 0, stdout=output)
