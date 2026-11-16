import test from 'node:test'
import assert from 'node:assert/strict'
import {request,readResponse} from '../src/composables/request.js'

test('deadline includes a stalled body and aborts the request',async t=>{
  t.mock.timers.enable({apis:['setTimeout']})
  let signal
  t.mock.method(globalThis,'fetch',async(_url,options)=>{
    signal=options.signal
    return {ok:true,json:()=>new Promise(()=>{})}
  })
  const result=request('/api/runs',{},response=>readResponse(response,'json'))
  const rejected=assert.rejects(result,{name:'QueryTimeoutError',message:'Query exceeded 500 ms: /api/runs'})
  t.mock.timers.tick(500)
  await rejected
  assert.equal(signal.aborted,true)
})

test('successful reads clear their deadline and stream cancellation remains connected',async t=>{
  t.mock.timers.enable({apis:['setTimeout']})
  let signal
  t.mock.method(globalThis,'fetch',async(_url,options)=>{signal=options.signal;return new Response('ok')})
  const parent=new AbortController()
  const response=await request('/api/events',{signal:parent.signal})
  assert.equal(await response.text(),'ok')
  t.mock.timers.tick(1000)
  assert.equal(signal.aborted,false)
  parent.abort()
  assert.equal(signal.aborted,true)
})
