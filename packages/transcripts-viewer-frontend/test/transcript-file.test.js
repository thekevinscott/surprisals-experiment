import test from 'node:test'
import assert from 'node:assert/strict'
import {transcriptFile} from '../src/composables/transcriptFile.js'
test('transcript file view retains all raw records and physical source lines',()=>{
  const raw=['{"role":"system","content":"instructions"}','','{"role":"assistant","content":"partial","_complete":false}','{"type":"provider_error","error":"failed"}','broken']
  const messages=transcriptFile(raw.join('\n'),'u/transcripts/messages.jsonl')
  assert.deepEqual(messages.map(m=>m.line),[1,3,4,5])
  assert.deepEqual(messages.map(m=>m.raw),raw.filter(Boolean))
  assert.deepEqual(messages.map(m=>m.role),['system','assistant','provider_error','Unparsed record'])
})
