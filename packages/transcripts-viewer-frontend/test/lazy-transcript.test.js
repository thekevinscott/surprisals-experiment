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

test('appended metadata retains loaded raw blocks without fetching new offscreen contents',()=>{
  const source='u/transcript.jsonl', url='/api/runs/run/files/cell/u/transcript.jsonl'
  const metadata={total:2,blocks:[{index:0,type:'system'},{index:1,type:'assistant'}]}
  const before=transcriptBlocks(metadata,source,url)
  before[0].raw='{"role":"system","content":"  prompt\\n\\n  "}'
  before[1].raw='{"role":"assistant","_complete":false}'
  const retained=before.map(message=>message.raw)
  const previousObserver=observeTranscriptBlocks(before,()=>()=>{})
  const after=transcriptBlocks({total:3,blocks:[...metadata.blocks,{index:2,type:'user'}]},source,url,before)
  previousObserver.dispose()
  assert.deepEqual(after.slice(0,2).map(message=>message.raw),retained)
  assert.equal(after[2].raw,undefined)
  const requests=[]
  const observer=observeTranscriptBlocks(after,(url,receive)=>{requests.push({url,receive});return ()=>{}})
  assert.equal(requests.length,0)
  observer.visible(1,true)
  assert.equal(requests.length,1)
  requests[0].receive({blocks:[{index:1,raw:'{"role":"assistant","content":"finished"}'}]})
  assert.equal(after[1].raw,'{"role":"assistant","content":"finished"}')
  assert.equal(after[2].raw,undefined)
  const other=transcriptBlocks(metadata,source,'/api/runs/other/files/cell/u/transcript.jsonl',before)
  assert.ok(other.every(message=>message.raw===undefined))
  observer.dispose()
})

test('disposing a transcript releases loaded raw contents and cannot hydrate after closure',()=>{
  const messages=transcriptBlocks({total:2,blocks:[{index:0,type:'user'},{index:1,type:'assistant'}]},'transcript.jsonl','/api/runs/run/files/transcript.jsonl')
  const callbacks=[],stopped=[]
  const observer=observeTranscriptBlocks(messages,(url,receive)=>{callbacks.push(receive);return ()=>stopped.push(url)})
  observer.visible(0,true);observer.visible(1,true)
  callbacks[0]({blocks:[{index:0,raw:'large user text'.repeat(10000)}]})
  callbacks[1]({blocks:[{index:1,raw:'large assistant text'.repeat(10000)}]})
  observer.dispose()
  assert.equal(stopped.length,2)
  assert.ok(messages.every(message=>message.raw===undefined),'closed modal must release every hydrated block')
  callbacks[0]({blocks:[{index:0,raw:'late response'}]})
  observer.visible(1,true)
  assert.ok(messages.every(message=>message.raw===undefined),'late callbacks must not resurrect contents')
  assert.equal(callbacks.length,2,'closed transcript must not reopen subscriptions')
})
