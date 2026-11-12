export function attemptState(attempt) {
  if (attempt?.generation?.timed_out) return 'Timed out'
  if (attempt?.generation?.error) return `Failed: ${attempt.generation.error}`
  if (!attempt?.tests) return 'Tests not recorded'
  const tests = attempt.tests
  return `${tests.all_passed ? 'Passed' : 'Failed'} · ${tests.passed}/${tests.total} tests passed`
}
export function turnSummary(turn) {
  const passed = turn.samples.filter(sample => sample.latest?.tests?.all_passed && !sample.latest.generation?.timed_out && !sample.latest.generation?.error).length
  return `${passed}/${turn.samples.length} samples passed · ${turn.measurement == null ? 'No score' : `${turn.measurement.toLocaleString(undefined, {maximumFractionDigits:2})} ${turn.unit}`}`
}
