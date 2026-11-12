import test from 'node:test'
import assert from 'node:assert/strict'
import {runDuration} from '../src/composables/runDuration.js'

test('open runs advance from invocation start; ended runs keep recorded duration',()=>{
  const started='2026-11-12T20:00:00Z', now=Date.parse('2026-11-12T20:10:00Z')
  assert.equal(runDuration({started,elapsed:0.3},now),600)
  assert.equal(runDuration({started,ended:'2026-11-12T20:02:00Z',elapsed:120},now),120)
  assert.equal(runDuration({elapsed:null},now),null)
})
