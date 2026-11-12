import test from 'node:test'
import assert from 'node:assert/strict'
import {watchData,liveSnapshot} from '../src/composables/liveUpdates.js'
class Events {
  static instances=[]
  listeners={}
  constructor(url){this.url=url;Events.instances.push(this)}
  addEventListener(name,fn){this.listeners[name]=fn}
  data(url,data){this.listeners.resource({data:JSON.stringify({url,data})})}
  close(){this.closed=true}
}
const tick=()=>new Promise(resolve=>setImmediate(resolve))
test('one multiplexed SSE connection, snapshots, reconnect and cleanup',async()=>{
  globalThis.EventSource=Events
  const a=new AbortController(),b=new AbortController(),values=[],errors=[]
  watchData(['/api/runs/a'],async()=>liveSnapshot('/api/runs/a'),{signal:a.signal,onData:v=>values.push(v),onError:e=>errors.push(e.message)})
  watchData(['/api/runs/b'],async()=>liveSnapshot('/api/runs/b'),{signal:b.signal,onData:v=>values.push(v),onError:e=>errors.push(e.message)})
  await tick();assert.equal(Events.instances.length,1)
  const stream=Events.instances[0]
  assert.deepEqual(JSON.parse(new URL(stream.url,'http://localhost').searchParams.get('resources')),['/api/runs/a','/api/runs/b'])
  stream.data('/api/runs/a','a');stream.data('/api/runs/b','b');await tick()
  assert.deepEqual(values,['a','b'])
  stream.data('/api/runs/a','changed');await tick();assert.deepEqual(values,['a','b','changed'])
  stream.data('/api/runs/a','changed');await tick();assert.equal(values.length,3,'unchanged reconnect snapshots do not rerender')
  stream.onerror();assert.equal(errors.length,2)
  stream.data('/api/runs/a','changed');await tick();assert.equal(values.length,4,'same data after an error clears reconnect state')
  stream.data('/api/runs/a','reconnected');await tick();assert.equal(values.at(-1),'reconnected')
  a.abort();b.abort();await tick();assert.equal(stream.closed,true)
  assert.equal(liveSnapshot('/api/runs/a'),undefined)
  delete globalThis.EventSource
})
test('waits for all resources, coalesces changes, and ignores cancelled reads',async()=>{
  globalThis.EventSource=Events
  const controller=new AbortController(),releases=[],values=[]
  watchData(['/api/runs/a','/api/runs/b'],()=>new Promise(resolve=>releases.push(resolve)),{
    signal:controller.signal,onData:v=>values.push(v),onError:e=>{throw e},
  })
  await tick();const stream=Events.instances.at(-1)
  stream.data('/api/runs/a',1);assert.equal(releases.length,0)
  stream.data('/api/runs/b',1);assert.equal(releases.length,1)
  stream.data('/api/runs/a',2);stream.data('/api/runs/b',2)
  releases[0]('old');await tick();assert.equal(releases.length,2)
  controller.abort();releases[1]('late');await tick()
  assert.deepEqual(values,['old']);assert.equal(stream.closed,true)
  delete globalThis.EventSource
})

test('opening a second view of the same file uses its current snapshot immediately',async()=>{
  globalThis.EventSource=Events
  const a=new AbortController(),b=new AbortController(),values=[]
  const url='/api/runs/a/files/question.txt'
  watchData([url],async()=>liveSnapshot(url),{signal:a.signal,onData:()=>{},onError:assert.fail})
  await tick();const stream=Events.instances.at(-1)
  stream.data(url,'question');await tick()
  watchData([url],async()=>liveSnapshot(url),{signal:b.signal,onData:value=>values.push(value),onError:assert.fail})
  await tick();assert.equal(Events.instances.at(-1),stream);assert.deepEqual(values,['question'])
  a.abort();b.abort();await tick();delete globalThis.EventSource
})
