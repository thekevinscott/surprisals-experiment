import Fastify from 'fastify'
import {Worker} from 'node:worker_threads'
import {createEvents} from './lib/events.js'

// One worker holds the single DirSQL instance for the experiment, off the HTTP
// event loop. Reuse unfinished reads instead of queuing another copy.
export function createWorkerApi(directory){
  const app=Fastify(),events=createEvents(),pending=new Map(),inflight=new Map()
  let sequence=0,worker
  function workerFor(){
    if(worker)return worker
    worker=new Worker(new URL('./query-worker.js',import.meta.url),{workerData:{directory}})
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
    const worker=workerFor()
    if(worker.failure)throw worker.failure
    let work=inflight.get(url)
    if(!work){
      const id=++sequence
      work=new Promise((resolve,reject)=>{
        pending.set(id,{resolve,reject,worker})
        worker.postMessage({id,url})
      }).finally(()=>inflight.delete(url))
      inflight.set(url,work)
    }
    return work
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
  app.addHook('onReady',async()=>{await workerFor().ready})
  app.addHook('onRequest',async(_request,reply)=>{reply.header('Cache-Control','no-store')})
  app.setErrorHandler((error,_request,reply)=>reply.code(error.statusCode??500).send({error:error.message}))
  app.addHook('preClose',async()=>events.close())
  app.addHook('onClose',async()=>{
    if(!worker||worker.threadId===-1)return
    await new Promise(resolve=>{worker.once('exit',resolve);worker.postMessage({close:true})})
  })
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
