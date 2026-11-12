import test from 'node:test'
import assert from 'node:assert/strict'
import {watchData,liveSnapshot,connected} from '../src/composables/liveUpdates.js'
class Events {
  static instances=[]
  constructor(url,options){
    this.resources=JSON.parse(options.body).resources
    this.response=new Response(new ReadableStream({start:controller=>{this.output=controller}}))
    options.signal.addEventListener('abort',()=>{if(!this.closed)this.output.close();this.closed=true},{once:true})
    Events.instances.push(this)
  }
  data(url,data){this.send('resource',{url,data})}
  send(type,data){this.output.enqueue(new TextEncoder().encode(`event: ${type}\ndata: ${JSON.stringify(data)}\n\n`))}
  fail(){this.closed=true;this.output.close()}
}
const tick=()=>new Promise(resolve=>setImmediate(resolve))
function mock(t){const original=globalThis.fetch;Events.instances=[];globalThis.fetch=async(url,options)=>new Events(url,options).response;t.after(()=>{globalThis.fetch=original})}
test('one multiplexed POST connection, snapshots, reconnect and cleanup',async t=>{
  mock(t)
  const a=new AbortController(),b=new AbortController(),values=[],errors=[]
  watchData(['/api/runs/a'],async()=>liveSnapshot('/api/runs/a'),{signal:a.signal,onData:v=>values.push(v),onError:e=>errors.push(e.message)})
  watchData(['/api/runs/b'],async()=>liveSnapshot('/api/runs/b'),{signal:b.signal,onData:v=>values.push(v),onError:e=>errors.push(e.message)})
  await tick();assert.equal(Events.instances.length,1)
  const stream=Events.instances[0]
  assert.deepEqual(stream.resources,['/api/runs/a','/api/runs/b'])
  stream.data('/api/runs/a','a');stream.data('/api/runs/b','b');await tick()
  assert.deepEqual(values,['a','b'])
  stream.data('/api/runs/a','changed');await tick();assert.deepEqual(values,['a','b','changed'])
  stream.data('/api/runs/a','changed');await tick();assert.equal(values.length,3,'unchanged reconnect snapshots do not rerender')
  stream.fail();await tick();assert.equal(errors.length,0);assert.equal(connected.value,false)
  await new Promise(resolve=>setTimeout(resolve,1100))
  const reconnected=Events.instances.at(-1);assert.notEqual(reconnected,stream);assert.equal(connected.value,true)
  reconnected.data('/api/runs/a','changed');await tick();assert.equal(values.length,4,'same data after an error clears reconnect state')
  reconnected.data('/api/runs/a','reconnected');await tick();assert.equal(values.at(-1),'reconnected')
  reconnected.send('stream-error',{url:'/api/runs/b',error:'not recorded'});await tick();assert.deepEqual(errors,['not recorded'])
  a.abort();b.abort();await tick();assert.equal(reconnected.closed,true)
  assert.equal(liveSnapshot('/api/runs/a'),undefined)
})
test('waits for all resources, coalesces changes, and ignores cancelled reads',async t=>{
  mock(t)
  const controller=new AbortController(),releases=[],values=[]
  watchData(['/api/runs/a','/api/runs/b'],()=>new Promise(resolve=>releases.push(resolve)),{
    signal:controller.signal,onData:v=>values.push(v),onError:e=>{throw e},
  })
  await tick();const stream=Events.instances.at(-1)
  stream.data('/api/runs/a',1);await tick();assert.equal(releases.length,0)
  stream.data('/api/runs/b',1);await tick();assert.equal(releases.length,1)
  stream.data('/api/runs/a',2);stream.data('/api/runs/b',2);await tick()
  releases[0]('old');await tick();assert.equal(releases.length,2)
  controller.abort();releases[1]('late');await tick()
  assert.deepEqual(values,['old']);assert.equal(stream.closed,true)
})
test('opening a second view of the same file uses its current snapshot immediately',async t=>{
  mock(t)
  const a=new AbortController(),b=new AbortController(),values=[]
  const url='/api/runs/a/files/question.txt'
  watchData([url],async()=>liveSnapshot(url),{signal:a.signal,onData:()=>{},onError:assert.fail})
  await tick();const stream=Events.instances.at(-1)
  stream.data(url,'question');await tick()
  watchData([url],async()=>liveSnapshot(url),{signal:b.signal,onData:value=>values.push(value),onError:assert.fail})
  await tick();assert.equal(Events.instances.at(-1),stream);assert.deepEqual(values,['question'])
  a.abort();b.abort();await tick()
})
