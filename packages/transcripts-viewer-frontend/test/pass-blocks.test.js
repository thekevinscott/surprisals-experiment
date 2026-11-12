import test from 'node:test'
import assert from 'node:assert/strict'
import {passBlocks, attemptOutcome, turnPassed, turnSummary} from '../src/composables/outcomes.js'

test('pass counts become one green block per pass and one red block per failure', () => {
  assert.deepEqual(passBlocks(5, 5), ['passed', 'passed', 'passed', 'passed', 'passed'])
  assert.deepEqual(passBlocks(4, 5), ['passed', 'passed', 'passed', 'passed', 'failed'])
  assert.deepEqual(passBlocks(0, 3), ['failed', 'failed', 'failed'])
  assert.deepEqual(passBlocks(0, 0), [])
})

test('sample labels distinguish recorded outcomes, generation failures, and unknown results', () => {
  assert.equal(attemptOutcome({tests: {all_passed: true}}), 'passed')
  assert.equal(attemptOutcome({tests: {all_passed: false}}), 'failed')
  assert.equal(attemptOutcome({generation: {timed_out: true}, tests: {all_passed: true}}), 'failed')
  assert.equal(attemptOutcome({generation: {error: 'provider failed'}}), 'failed')
  assert.equal(attemptOutcome({}), 'unknown')
  assert.equal(attemptOutcome(null), 'unknown')
  const turn = {samples: [{latest: {tests: {all_passed: true}}}, {latest: {tests: {all_passed: false}}}, {}], measurement: 12, unit: 'bits'}
  assert.equal(turnPassed(turn), 1)
  assert.equal(turnSummary(turn), '12 bits')
  assert.equal(turnSummary({...turn, measurement: null}), 'No score')
})

test('turn scores retain their exact numeric string without locale rounding',()=>{
 assert.equal(turnSummary({measurement:1234.567890123,unit:'bits'}),'1234.567890123 bits')
})
