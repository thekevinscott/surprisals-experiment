import test from 'node:test'
import assert from 'node:assert/strict'
import {Worker} from 'node:worker_threads'
import {createWorkerApi} from '../worker-api.js'

test('HTTP requests time out while worker work remains unfinished, without duplicate reads',async t=>{
  const sent=[]
  t.mock.method(Worker.prototype,'postMessage',function(message){sent.push({worker:this,...message})})
  const api=createWorkerApi('/tmp')
  t.after(()=>api.close())
  const first=await api.inject('/api/runs/index')
  assert.equal(first.statusCode,504)
  assert.match(first.json().error,/exceeded 500 ms/)
  const second=api.inject('/api/runs/index')
  await new Promise(resolve=>setImmediate(resolve))
  assert.equal(sent.length,1,'a timed-out read is not queued again while still running')
  sent[0].worker.emit('message',{id:sent[0].id,response:{status:200,type:'application/json',body:'{"rows":[]}'}})
  assert.equal((await second).statusCode,200)
})
