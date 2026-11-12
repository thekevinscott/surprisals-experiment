// One live query per subscribed endpoint, shared by direct and multiplexed SSE
// clients. Poll only while subscribed, never overlap reads, and send only changed
// snapshots. This avoids installing hundreds of thousands of filesystem watches.
export function createEvents({interval=2000}={}) {
  const resources=new Map(),clients=new Set()
  let closed=false
  function subscribe(key,load,onData,onError,seed) {
    let resource=resources.get(key)
    if(!resource){
      resource={listeners:new Set(),last:seed===undefined?undefined:JSON.stringify(seed),error:null,running:false,timer:null}
      resources.set(key,resource)
    }
    if(seed!==undefined&&resource.last!==JSON.stringify(seed)){
      resource.last=JSON.stringify(seed);resource.error=null
      for(const listener of resource.listeners)listener.onData(seed)
    }
    const listener={onData,onError}
    resource.listeners.add(listener)
    if(resource.last!==undefined)onData(JSON.parse(resource.last))
    if(resource.error)onError(JSON.parse(resource.error))
    async function refresh(){
      if(resource.running||closed||!resource.listeners.size)return
      resource.running=true
      try{
        const value=await load()
        if(closed||!resource.listeners.size)return
        const next=JSON.stringify(value)
        if(next!==resource.last||resource.error){
          resource.last=next;resource.error=null
          for(const listener of resource.listeners)listener.onData(value)
        }
      }catch(error){
        if(closed||!resource.listeners.size)return
        const value={error:error.message,status:error.statusCode??(error.code==='ENOENT'?404:400)},next=JSON.stringify(value)
        if(next!==resource.error){resource.error=next;for(const listener of resource.listeners)listener.onError(value)}
      }finally{
        resource.running=false
        if(!closed&&resource.listeners.size)resource.timer=setTimeout(refresh,interval)
      }
    }
    if(!resource.running&&!resource.timer)void refresh()
    return ()=>{
      resource.listeners.delete(listener)
      if(!resource.listeners.size){
        clearTimeout(resource.timer);resource.timer=null
        resource.last=undefined;resource.error=null
        resources.delete(key)
      }
    }
  }
  function headers(reply) {
    reply.hijack()
    reply.raw.writeHead(200,{'Content-Type':'text/event-stream; charset=utf-8','Cache-Control':'no-cache, no-transform',Connection:'keep-alive','X-Accel-Buffering':'no'})
    reply.raw.write('retry: 1000\n\n')
    clients.add(reply.raw)
    const heartbeat=setInterval(()=>reply.raw.write(': heartbeat\n\n'),15000)
    reply.raw.on('close',()=>{clearInterval(heartbeat);clients.delete(reply.raw)})
  }
  function send(reply,event,value){
    if(reply.raw.destroyed)return
    if(reply.raw.writableLength>64*1024*1024){reply.raw.destroy();return}
    reply.raw.write(`event: ${event}\ndata: ${JSON.stringify(value)}\n\n`)
  }
  async function stream(request,reply,load){
    const initial=await load() // Preserve HTTP status for missing or unsafe paths.
    if(reply.raw.destroyed)return
    headers(reply)
    const off=subscribe(request.url,load,value=>send(reply,'data',value),error=>send(reply,'stream-error',error),initial)
    reply.raw.on('close',off)
  }
  function multiplex(reply,urls,load){
    headers(reply)
    const stops=urls.map(url=>subscribe(url,()=>load(url),data=>send(reply,'resource',{url,data}),error=>send(reply,'stream-error',{url,...error})))
    reply.raw.on('close',()=>stops.forEach(stop=>stop()))
  }
  return {stream,multiplex,close(){
    closed=true
    for(const client of clients)client.end()
    for(const resource of resources.values()){clearTimeout(resource.timer);resource.listeners.clear();resource.last=undefined;resource.error=null}
    resources.clear()
  }}
}
