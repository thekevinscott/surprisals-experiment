import test from 'node:test'
import assert from 'node:assert/strict'
import { recordPresentation } from '../src/composables/recordPresentation.js'

test('content stays exact and every other field is metadata', () => {
  const record = { content: '  Read `n`.\n\nPrint max.  ', role: 'assistant', reasoning: 'Keep it short.', reasoning_details: [{ text: 'Keep it short.' }], _complete: true }
  const result = recordPresentation(JSON.stringify(record))
  assert.equal(result.text, record.content)
  assert.deepEqual({ content: result.text, ...result.metadata }, record)
})
test('nested T records retain envelope and message metadata; invalid JSON stays raw', () => {
  const record = { id: 'a', type: 'message', message: { role: 'assistant', content: 'text', usage: { tokens: 4 } } }
  assert.deepEqual(recordPresentation(JSON.stringify(record)), { text: 'text', metadata: { id: 'a', type: 'message', message: { role: 'assistant', usage: { tokens: 4 } } } })
  assert.deepEqual(recordPresentation('{unfinished'), { text: '{unfinished' })
})
test('T structured content renders text, reasoning and tool calls readably',()=>{
 const result=recordPresentation(JSON.stringify({type:'message',message:{role:'assistant',content:[{type:'thinking',thinking:'Think.'},{type:'text',text:'Answer.'},{type:'toolCall',name:'write',arguments:{path:'main.py'}}]}}))
 assert.equal(result.text,'Think.\n\nAnswer.\n\nwrite\n{\n  "path": "main.py"\n}')
})
test('U reasoning is exposed for display alongside unchanged content',()=>{
 const result=recordPresentation(JSON.stringify({role:'assistant',content:'Answer',reasoning:'Think\ncarefully'}));assert.equal(result.reasoning,'Think\ncarefully');assert.equal(result.text,'Answer')
})
