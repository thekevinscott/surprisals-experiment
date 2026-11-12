import test from 'node:test'
import assert from 'node:assert/strict'
import {tTranscript} from '../src/composables/tTranscript.js'
test('T session records do not occupy transcript message slots',()=>{
 const lines=[JSON.stringify({type:'session'}),JSON.stringify({type:'message',message:{role:'user',content:'Question'}})].join('\n')
 assert.equal(tTranscript(lines,'a.jsonl')[0].role,'user')
})
