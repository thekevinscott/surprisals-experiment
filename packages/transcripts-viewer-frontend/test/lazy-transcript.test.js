import test from 'node:test'
import assert from 'node:assert/strict'
import {transcriptBlocks, observeTranscriptBlocks} from '../src/composables/lazyTranscript.js'

test('metadata retains the complete ordered list, fetching only blocks intersecting the viewport', () => {
  const source='u/transcript.jsonl', url='/api/runs/run/files/cell/u/transcript.jsonl'
  const types=['system','user','system','Unparsed record','assistant','Unparsed record']
  const messages=transcriptBlocks({total:6,blocks:types.map((type,index)=>({index,type}))},source,url)
  const requests=[],stopped=[]
  const observer=observeTranscriptBlocks(messages,(url,receive)=>{
    requests.push({url,receive})
    return ()=>stopped.push(url)
  })
  assert.equal(messages.length,6)
  assert.deepEqual(messages.map(message=>message.role),types)
  assert.deepEqual(messages.map(message=>message.line),[1,2,3,4,5,6])
  assert.ok(messages.every(message=>message.raw===undefined))
  assert.equal(requests.length,0)
  observer.visible(4,true)
  observer.visible(4,true)
  assert.deepEqual(requests.map(request=>request.url),['/api/runs/run/transcript-blocks/4/5/cell/u/transcript.jsonl'])
  const raw='{"role":"assistant","content":"  first\\n\\nlast  ","_complete":false}'
  requests[0].receive({blocks:[{index:4,raw}]})
  assert.equal(messages[4].raw,raw)
  assert.ok(messages.filter((_,index)=>index!==4).every(message=>message.raw===undefined))
  observer.visible(4,false)
  assert.deepEqual(stopped,[requests[0].url])
  assert.equal(messages[4].raw,raw)
  observer.dispose()
})

test('scrolling all blocks preserves repeated prompts, blank lines, incomplete records, and live edits verbatim',()=>{
  const raw=['{"role":"system","content":"prompt"}','{"role":"system","content":"prompt"}','  ','{"role":"assistant","_complete":false}','']
  const messages=transcriptBlocks({total:5,blocks:raw.map((_,index)=>({index,type:'Record'}))},'transcript.jsonl','/api/runs/run/files/transcript.jsonl')
  const active=new Map()
  const observer=observeTranscriptBlocks(messages,(url,receive)=>{active.set(url,receive);return ()=>active.delete(url)})
  for(let index=0;index<raw.length;index++){
    observer.visible(index,true)
    active.get(`/api/runs/run/transcript-blocks/${index}/${index+1}/transcript.jsonl`)({blocks:[{index,raw:raw[index]}]})
    observer.visible(index,false)
  }
  assert.equal(messages.map(message=>message.raw).join('\n'),raw.join('\n'))
  observer.visible(3,true)
  active.values().next().value({blocks:[{index:3,raw:'{"role":"assistant","content":"new"}'}]})
  assert.equal(messages[3].raw,'{"role":"assistant","content":"new"}')
  observer.dispose()
  assert.equal(active.size,0)
})
