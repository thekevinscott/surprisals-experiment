import subprocess


def respond(state, args, **kwargs):
    if args[0] == "ssh" and "cat > /srv/aws-runner/command.sh" in args[-1]:
        state["shipped"] = True
    if args[0] == "ssh" and args[-1] == "test -f /srv/aws-runner/command.sh":
        return subprocess.CompletedProcess(args, 0 if state["shipped"] else 1)
    if args[:3] == ["git", "rev-parse", "--show-toplevel"]:
        output = state["checkout"]
    elif args[:3] == ["git", "rev-parse", "HEAD"]:
        output = "abc123\n"
    elif args[:3] == ["git", "status", "--porcelain"]:
        output = " M experiment.py\n"
    elif args[0] == "ssh" and "if [ -f" in args[-1] and not state["shipped"]:
        output = ""
    elif args[0] == "ssh" and "if [ -f" in args[-1]:
        output = state["polls"].pop(0) if len(state["polls"]) > 1 else state["polls"][0]
        if isinstance(output, int):
            raise subprocess.CalledProcessError(output, args)
    elif args[0] == "ssh" and "is-active" in args[-1]:
        output = state.get("unit", "inactive")
    else:
        output = ""
    if (
        "--unit=aws-runner " in args[-1]
        and "--collect" not in args[-1]
        and state.get("unit") == "failed"
    ):
        raise subprocess.CalledProcessError(1, args)
    if args[0] == "rsync" and args[-2].startswith("ubuntu@") and state["fail_copy"]:
        raise subprocess.CalledProcessError(23, args)
    if args[0] == "rsync" and args[-2].startswith("ubuntu@"):
        codes = state.get("copy_codes", [state.get("copy_code", 0)])
        code = codes.pop(0) if len(codes) > 1 else codes[0]
        return subprocess.CompletedProcess(args, code)
    return subprocess.CompletedProcess(args, 0, stdout=output)
