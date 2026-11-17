import test from 'node:test'
import assert from 'node:assert/strict'
import {Worker} from 'node:worker_threads'
import {mkdtemp,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {createWorkerApi} from '../worker-api.js'

test('concurrent requests share the unfinished worker read',async t=>{
  const sent=[],postMessage=Worker.prototype.postMessage
  t.mock.method(Worker.prototype,'postMessage',function(message){
    if(message.close)return postMessage.call(this,message)
    sent.push({worker:this,...message})
  })
  const root=await mkdtemp(join(tmpdir(),'viewer-worker-')),api=createWorkerApi(root)
  t.after(async()=>{await api.close();await rm(root,{recursive:true,force:true})})
  await api.ready()
  const first=api.inject('/api/runs/index'),second=api.inject('/api/runs/index')
  // Start both lazy injection promises before returning the worker response.
  const results=Promise.all([first,second])
  await new Promise(setImmediate)
  assert.equal(sent.length,1)
  sent[0].worker.emit('message',{id:sent[0].id,response:{status:200,type:'application/json',body:'{"rows":[]}'}})
  for(const response of await results){assert.equal(response.statusCode,200);assert.deepEqual(response.json(),{rows:[]})}
})
