import Fastify from 'fastify'
import {Worker} from 'node:worker_threads'
import {createEvents} from './lib/events.js'

const budget=500
const timeout=url=>Object.assign(Error(`Query exceeded ${budget} ms: ${url}`),{statusCode:504})

// Keep synchronous indexing and SQLite work off the HTTP event loop so the
// deadline can fire even while a query blocks. Reuse unfinished reads instead
// of queuing another copy on every stream refresh after a timeout. Costs use
// a separate worker so experiment-wide transcript ingestion cannot block an
// individual run or transcript request.
export function createWorkerApi(directory){
  const app=Fastify(),events=createEvents(),pending=new Map(),inflight=new Map()
  const workers=new Map()
  let sequence=0
  function workerFor(url){
    const group=url==='/api/runs'||url==='/api/runs/costs'||url.endsWith('/summary')?'costs':'details'
    if(workers.has(group))return workers.get(group)
    const worker=new Worker(new URL('./query-worker.js',import.meta.url),{workerData:{directory}})
    workers.set(group,worker)
    worker.ready=new Promise((resolve,reject)=>{
      worker.once('error',reject)
      worker.on('message',message=>{if(message.ready)resolve()})
    })
    worker.on('message',({id,response,error})=>{
      const request=pending.get(id)
      if(!request)return
      pending.delete(id)
      if(error)request.reject(Error(error));else request.resolve(response)
    })
    function fail(error){
      worker.failure=error
      for(const [id,request] of pending)if(request.worker===worker){request.reject(error);pending.delete(id)}
    }
    worker.on('error',fail)
    worker.on('exit',()=>fail(Error('Query worker stopped')))
    return worker
  }
  async function query(url){
    const worker=workerFor(url)
    if(worker.failure)throw worker.failure
    let work=inflight.get(url)
    if(!work){
      const id=++sequence
      work=new Promise((resolve,reject)=>{
        pending.set(id,{resolve,reject,worker})
        worker.postMessage({id,url,expires:Date.now()+budget})
      }).finally(()=>inflight.delete(url))
      inflight.set(url,work)
    }
    let timer
    const start=performance.now()
    try{
      const result=await Promise.race([work,new Promise((_,reject)=>{timer=setTimeout(()=>reject(timeout(url)),budget)})])
      if(performance.now()-start>=budget)throw timeout(url)
      return result
    }finally{clearTimeout(timer)}
  }
  async function value(url){
    const response=await query(url),body=Buffer.from(response.body).toString('utf8')
    if(response.status>=400){
      let message=body
      try{message=JSON.parse(body).error??body}catch{}
      throw Object.assign(Error(message),{statusCode:response.status})
    }
    return response.type?.startsWith('application/json')?JSON.parse(body):body
  }
  app.addHook('onReady',async()=>{await Promise.all([workerFor('/api/runs').ready,workerFor('/api/runs/index').ready])})
  app.addHook('onRequest',async(_request,reply)=>{reply.header('Cache-Control','no-store')})
  app.setErrorHandler((error,_request,reply)=>reply.code(error.statusCode??500).send({error:error.message}))
  app.addHook('preClose',async()=>events.close())
  app.addHook('onClose',async()=>{await Promise.all([...workers.values()].map(worker=>{
    if(worker.threadId===-1)return
    return new Promise(resolve=>{worker.once('exit',resolve);worker.postMessage({close:true})})
  }))})
  function stream(reply,urls){
    if(!Array.isArray(urls)||urls.some(url=>typeof url!=='string'||!/^\/api\/runs(?:\/|$)/.test(url)||/[?#\r\n]/.test(url)))throw Object.assign(Error('Expected an array of API resource paths'),{statusCode:400})
    return events.multiplex(reply,[...new Set(urls)],value)
  }
  app.get('/api/events',async(request,reply)=>stream(reply,JSON.parse(request.query.resources??'[]')))
  app.post('/api/events',async(request,reply)=>stream(reply,request.body?.resources))
  app.get('/api/*',async(request,reply)=>{
    if(request.headers.accept?.includes('text/event-stream'))return events.stream(request,reply,()=>value(request.url))
    const response=await query(request.url)
    if(response.type)reply.type(response.type)
    return reply.code(response.status).send(Buffer.from(response.body))
  })
  return app
}
