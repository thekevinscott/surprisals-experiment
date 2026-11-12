export function attemptState(attempt) {
  if (attempt?.generation?.timed_out) return 'Timed out'
  if (attempt?.generation?.error) return `Failed: ${attempt.generation.error}`
  if (!attempt?.tests) return 'Tests not recorded'
  const tests = attempt.tests
  return `${tests.all_passed ? 'Passed' : 'Failed'} · ${tests.passed}/${tests.total} tests passed`
}
export function turnSummary(turn) {
  return turn.measurement == null ? 'No score' : `${turn.measurement.toLocaleString(undefined, {maximumFractionDigits:2})} ${turn.unit}`
}

export function passBlocks(passed, total) {
  return Array.from({length: total}, (_, index) => index < passed ? 'passed' : 'failed')
}
export function attemptOutcome(attempt) {
  if (attempt?.generation?.timed_out || attempt?.generation?.error) return 'failed'
  if (attempt?.tests?.all_passed == null) return 'unknown'
  return attempt.tests.all_passed ? 'passed' : 'failed'
}
export function turnPassed(turn) {
  return turn.samples.filter(sample => attemptOutcome(sample.latest) === 'passed').length
}
