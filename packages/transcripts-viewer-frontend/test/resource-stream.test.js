import test from 'node:test'
import assert from 'node:assert/strict'
import {ResourceStream} from '../src/composables/resourceStream.js'
const tick=()=>new Promise(resolve=>setImmediate(resolve))
test('POST subscription keeps large resource sets out of URLs and decodes split SSE frames',async()=>{
  const original=globalThis.fetch,requests=[],events=[]
  let output
  globalThis.fetch=async(url,options)=>{requests.push({url,options});return new Response(new ReadableStream({start(controller){output=controller}}),{headers:{'Content-Type':'text/event-stream'}})}
  const resources=Array.from({length:300},(_,i)=>`/api/runs/a/files/${i}`)
  const stream=new ResourceStream(resources)
  stream.addEventListener('resource',event=>events.push(JSON.parse(event.data)))
  try{
    await tick();assert.equal(requests[0].url,'/api/events');assert.equal(requests[0].options.method,'POST')
    assert.deepEqual(JSON.parse(requests[0].options.body),{resources})
    const bytes=new TextEncoder().encode('retry: 1000\n\nevent: resource\ndata: {"url":"/api/runs/a/files/0","data":"é"}\n\n')
    output.enqueue(bytes.slice(0,bytes.length-4));await tick();assert.deepEqual(events,[])
    output.enqueue(bytes.slice(bytes.length-4));await tick();assert.equal(events[0].data,'é')
    stream.close();assert.equal(requests[0].options.signal.aborted,true)
  }finally{stream.close();globalThis.fetch=original}
})
