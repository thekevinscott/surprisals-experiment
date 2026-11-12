import test from 'node:test'
import assert from 'node:assert/strict'
import {testCaseBlocks} from '../src/composables/outcomes.js'

test('test blocks preserve case order and target array positions, not case IDs or grouped counts', () => {
  const cases = [{index: 10, passed: false}, {index: 3, passed: true}, {index: 21, passed: false}]
  assert.deepEqual(testCaseBlocks(cases), [
    {outcome: 'failed', index: 10, position: 0},
    {outcome: 'passed', index: 3, position: 1},
    {outcome: 'failed', index: 21, position: 2},
  ])
  assert.deepEqual(testCaseBlocks([]), [])
})
