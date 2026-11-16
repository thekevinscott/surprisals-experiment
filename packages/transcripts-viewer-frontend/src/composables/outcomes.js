export function attemptState(attempt) {
  if (attempt?.generation?.timed_out) return 'Timed out'
  if (attempt?.generation?.error) return `Failed: ${attempt.generation.error}`
  if (!attempt?.tests) return 'Tests not recorded'
  const tests = attempt.tests
  return `${tests.all_passed ? 'Passed' : 'Failed'} · ${tests.passed}/${tests.total} tests passed`
}
export function turnSummary(turn) {
  return turn.measurement == null ? 'No score' : `${turn.unit==='bits' ? Number(turn.measurement.toFixed(3)) : turn.measurement} ${turn.unit}`
}

export const attemptOutcome = attempt => attempt?.outcome??'unknown'
export function testCaseBlocks(cases=[]) {
  return cases.map((test, position) => ({status: test.status, index: test.index, position}))
}

export const transcriptFailure = attempt => attempt.failure
