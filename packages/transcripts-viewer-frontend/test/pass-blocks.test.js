import test from 'node:test'
import assert from 'node:assert/strict'
import {passBlocks} from '../src/composables/outcomes.js'

test('pass counts become one green block per pass and one red block per failure', () => {
  assert.deepEqual(passBlocks(5, 5), ['passed', 'passed', 'passed', 'passed', 'passed'])
  assert.deepEqual(passBlocks(4, 5), ['passed', 'passed', 'passed', 'passed', 'failed'])
  assert.deepEqual(passBlocks(0, 3), ['failed', 'failed', 'failed'])
  assert.deepEqual(passBlocks(0, 0), [])
})
