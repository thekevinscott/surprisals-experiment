import test from 'node:test'
import assert from 'node:assert/strict'
import {runStatus,runCounts} from '../src/composables/runStatus.js'

test('status combines ended-run diagnostics and omits them for open invocations',()=>{
  assert.equal(runStatus({status:'Open',exit:null}), 'Open')
  assert.equal(runStatus({status:'Open',exit:null,cause:'stale reason'}), 'Open')
  assert.equal(runStatus({status:'Complete',ended:'2026-11-12',exit:0,cause:null}), 'success')
  assert.equal(runStatus({status:'Stopped / failed',ended:'2026-11-12',exit:1,cause:'provider failed'}), 'Stopped / failed · exit 1 · provider failed')
  assert.equal(runStatus({status:'Stopped / failed',ended:'2026-11-12',exit:null,cause:'interrupted'}), 'Stopped / failed · interrupted')
})

test('run counts report completed over total',()=>{
  assert.equal(runCounts([{status:'Complete'},{status:'Open'},{status:'Stopped / failed'}]), '1 / 3 complete')
})
