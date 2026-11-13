import test from 'node:test'
import assert from 'node:assert/strict'
import {openTranscript,stepUTurn,filePreview,closeFile} from '../src/composables/filePreview.js'

test('U navigation follows existing turns, updates request/header, respects ends and discovers new turns',()=>{
 const context={window:1,fork:2,turn:3,turns:[{id:0,metadata:{u_messages:2,error:'failed'}},{id:3,metadata:{u_messages:5,u_request_sha256:'hash3'}},{id:9,metadata:{u_messages:11,u_request_sha256:'hash9'}}]}
 const file={source:'windows/1/forks/2/u/transcript.jsonl',url:'/api/files/transcript.jsonl'}
 openTranscript({name:'U transcript',uView:true,uNavigation:()=>context,files:[file]})
 assert.match(filePreview.value.name,/Window 1 · Fork 2 · Turn 3/);assert.match(filePreview.value.name,/hash3/)
 stepUTurn(-1);assert.equal(filePreview.value.turnMetadata.u_messages,2);assert.equal(filePreview.value.turnMetadata.error,'failed')
 stepUTurn(-1);assert.equal(filePreview.value.uTurnId,0)
 stepUTurn(1);stepUTurn(1);assert.equal(filePreview.value.uTurnId,9);assert.equal(filePreview.value.turnMetadata.u_messages,11)
 stepUTurn(1);assert.equal(filePreview.value.uTurnId,9)
 context.turns.push({id:12,metadata:{u_messages:17,u_request_sha256:'hash12'}})
 stepUTurn(1);assert.equal(filePreview.value.uTurnId,12);assert.match(filePreview.value.name,/hash12/)
 assert.deepEqual(filePreview.value.files,[file]);assert.equal(filePreview.value.source,file.source)
 closeFile();stepUTurn(1);assert.equal(filePreview.value,null)
 openTranscript({name:'T transcript',files:[file]});stepUTurn(1);assert.equal(filePreview.value.name,'T transcript');closeFile()
})
