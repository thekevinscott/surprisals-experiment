import test from 'node:test'
import assert from 'node:assert/strict'
import {transcriptFile} from '../src/composables/transcriptFile.js'
test('transcript file view retains all raw records and physical source lines',()=>{
  const raw=['{"role":"system","content":"instructions"}','','{"role":"assistant","content":"partial","_complete":false,"timestamp":"2026-01-01T00:00:00+00:00","completion_id":"u","usage":{"completion_tokens":3}}','{"type":"provider_error","error":"failed"}','broken']
  const messages=transcriptFile(raw.join('\n'),'u/transcript.jsonl')
  assert.deepEqual(messages.map(m=>m.line),[1,2,3,4,5])
  assert.deepEqual(messages.map(m=>m.raw),raw)
  assert.deepEqual(messages.map(m=>m.role),['system','','assistant','provider_error',''])
})

test('repeated system prompts, resets, whitespace and incomplete records stay byte-for-byte in order',()=>{
  const text='{"role":"system","content":"first"}\r\n  \n{"role":"system","content":"second","_reset":true}\n{"role":"assistant","_complete":false}\n'
  const messages=transcriptFile(text,'transcript.jsonl')
  assert.equal(messages.filter(m=>m.role==='system').length,2)
  assert.equal(messages.map(m=>m.raw).join('\n')+'\n',text)
})

test('a final newline is a terminator, not a phantom record; real blank lines remain',()=>{
  assert.deepEqual(transcriptFile('', 'x'),[])
  assert.deepEqual(transcriptFile('a\n\nb\n','x').map(m=>m.raw),['a','','b'])
  assert.deepEqual(transcriptFile('a\n\n','x').map(m=>m.raw),['a',''])
  assert.deepEqual(transcriptFile('\n','x').map(m=>m.raw),[''])
})
