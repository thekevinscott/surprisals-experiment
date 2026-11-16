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


test('cost work cannot block a run detail response',async t=>{
  const sent=[]
  t.mock.method(Worker.prototype,'postMessage',function(message){sent.push({worker:this,...message})})
  const api=createWorkerApi('/tmp')
  t.after(()=>api.close())
  const costs=api.inject('/api/runs/costs')
  const details=api.inject('/api/runs/one/details')
  await new Promise(resolve=>setImmediate(resolve))
  assert.equal(sent.length,2)
  assert.notEqual(sent[0].worker,sent[1].worker)
  const detail=sent.find(request=>request.url.endsWith('/details'))
  detail.worker.emit('message',{id:detail.id,response:{status:200,type:'application/json',body:'{"row":{"elapsed":42}}'}})
  assert.equal((await details).json().row.elapsed,42)
  assert.equal((await costs).statusCode,504)
})
