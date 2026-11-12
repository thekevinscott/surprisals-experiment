export function runDuration(run, now) {
  if (!run.started) return run.elapsed
  return Math.max(0, ((run.ended ? Date.parse(run.ended) : now) - Date.parse(run.started)) / 1000)
}
