# Surprisals Experiment — agent instructions

## Initiative and scope

- Act on agreed fixes within the current task. If you conclude that code should
  change, make the change and verify it; do not stop at “I would change this” or
  ask Kevin to repeat an instruction he has already given.
- Carry authorized work through to completion, including updating an active PR
  when the review calls for a change. Report what you changed and checked.
- Be proactive about completing the requested work, not expanding its scope.
  Do not invent features, change experimental conditions, or add behavior Kevin
  did not request. Preserve explicit requests to discuss first or hold off.
- Prefer the smallest clear implementation. Avoid speculative abstractions,
  configuration options, fallback paths, and defensive checks without a concrete
  requirement. Less code is better when it satisfies the task.
- Ask only when a missing decision materially affects scope or correctness and
  cannot be resolved from the conversation. Continue independent work meanwhile.
- This project is never built or published as a package; it runs from source.
  Do not check wheel builds or package-data config.

## Completion and recovery

- Track the requested outcome and outstanding commitments in the session handoff.
  Before ending a task, check each commitment against evidence: implementation,
  validation, deployment, completed runs, and artifact uploads as applicable.
  A process exiting or a status report being written does not establish completion.
- Infrastructure failures leave an experiment unfinished. Diagnose and retry
  within the authorized scope and budget; preserve failed runs. Do not change
  prompts, caps, models, or success criteria to get a passing result. Repeated
  failures with no viable recovery are a blocker to report, not task completion
  or permission to keep spending indefinitely.
- For a local/remote experiment comparison, obtain a valid result on each host
  (success or exhaustion of the configured attempts), verify the artifacts, and
  complete the requested uploads. A provider error is not a valid final result.

## Improve the workflow

- When Kevin identifies a recurring workflow failure, turn the lesson into the
  smallest relevant instruction or tooling change and open or update a PR.
  A promise in chat is not the deliverable. Honor an explicit request to discuss
  first or make no edits; otherwise, carry the improvement through to review.
- Write corrections as observable actions and completion checks, not adjectives
  such as "be proactive." Check the proposed rule against the failure that
  prompted it, and keep advancing the original task while making the improvement.

## Pull request targets

- Every PR must target `main`. Never target another feature branch or PR branch,
  and never create a stacked PR chain.
- Before creating or retargeting a PR, verify its base is `main`. After creating
  it, verify the base again with `gh pr view --json baseRefName`.
- If a change depends on an unmerged PR, wait for that dependency to merge into
  `main`, then rebase onto `main`. Do not merge work into the dependency branch.

## Banking runs

- Bank every run in the Hugging Face dataset
  `thekevinscott/surprisals-experiment-runs`, at the same `{experiment}/{run}`
  path it has under `runs/`. Bank before deleting a run from any host.
- Upload from the host holding the full run (usually `optimizing`), from the
  repo root, one commit per run cell so each stays a few thousand files:

  ```sh
  uv run --no-project --env-file .env --with huggingface-hub \
    hf upload thekevinscott/surprisals-experiment-runs \
    runs/EXP/RUN/CELL EXP/RUN/CELL --repo-type dataset
  ```

  Then upload the invocation's own files with `runs/EXP/RUN EXP/RUN --exclude "*/*"`.
- Do not `git push` from the `runs/` clone. `optimizing` has no git-lfs, and the
  dataset's `.gitattributes` routes `*.json` to LFS.
- Done means the file count under `EXP/RUN` on the Hub equals
  `find runs/EXP/RUN -type f | wc -l` on the host. Delete only after that.
