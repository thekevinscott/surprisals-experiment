import test from 'node:test'
import assert from 'node:assert/strict'
import {runDuration} from '../src/composables/runDuration.js'

test('duration displays server-computed active runtime across restarts and live updates',()=>{
 const row={started:'2026-11-01T13:00:00Z',elapsed:13800}
 assert.equal(runDuration(row),13800)
 row.elapsed=13801
 assert.equal(runDuration(row),13801)
 assert.equal(runDuration({...row,ended:'2026-11-01T14:00:00Z',elapsed:13800}),13800)
 assert.equal(runDuration({elapsed:null}),null)
})
