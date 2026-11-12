import test from 'node:test'
import assert from 'node:assert/strict'
import { uContext } from '../lib/u-context.js'
import { parseUTranscript } from '../lib/experiment.js'
test('U context mirrors system replacement, reset and incomplete-reply exclusion', () => {
  const entries = [
    {role:'system',content:'initial'}, {role:'system',content:'turn0'},
    {role:'user',content:'question',_reset:true}, {role:'assistant',content:'a',_complete:true},
    {role:'system',content:'turn1'}, {role:'user',content:'reset',_reset:true},
    {role:'assistant',content:'partial',_complete:false}, {role:'assistant',content:'b',_complete:true},
    {role:'system',content:'turn2'}, {role:'user',content:'continue'}, {role:'assistant',content:'c',_complete:true},
  ]
  const {replies,messages} = parseUTranscript(entries.map(JSON.stringify).join('\n'),'messages.jsonl')
  assert.deepEqual(replies.map(r=>uContext(messages,r.context).map(m=>messages.indexOf(m))), [[1,2,3],[4,5,7],[8,5,7,9,10]])
})
test('U source line numbers survive blank lines',()=>{const {messages}=parseUTranscript('\n'+JSON.stringify({role:'user',content:'q'})+'\n\n'+JSON.stringify({role:'assistant',content:'a',_complete:true}),'u.jsonl');assert.deepEqual(messages.map(m=>m.line),[2,4])})
