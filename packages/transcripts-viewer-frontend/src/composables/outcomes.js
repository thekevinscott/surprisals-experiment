export function attemptState(attempt) {
  if (attempt?.generation?.timed_out) return 'Timed out'
  if (attempt?.generation?.error) return `Failed: ${attempt.generation.error}`
  if (!attempt?.tests) return 'Tests not recorded'
  const tests = attempt.tests
  return `${tests.all_passed ? 'Passed' : 'Failed'} · ${tests.passed}/${tests.total} tests passed`
}
export function turnSummary(turn) {
  return turn.measurement == null ? 'No score' : `${String(turn.measurement)} ${turn.unit}`
}

export function attemptOutcome(attempt) {
  if (attempt?.generation?.timed_out || attempt?.generation?.error) return 'failed'
  if (attempt?.tests?.all_passed == null) return 'unknown'
  return attempt.tests.all_passed ? 'passed' : 'failed'
}
export function testCaseBlocks(cases=[]) {
  return cases.map((test, position) => ({status: test.status, index: test.index, position}))
}
