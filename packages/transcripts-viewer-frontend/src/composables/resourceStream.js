import {request,queryTimeout} from './request.js'
// A single POST SSE connection avoids URL-size and browser connection limits
// as a live run accumulates samples and visible transcript blocks.
export class ResourceStream {
  constructor(resources) {
    this.resources=resources
    this.listeners=new Map()
    this.controller=new AbortController()
    this.closed=false
    void this.connect()
  }
  addEventListener(type,listener) { this.listeners.set(type,listener) }
  close() {
    this.closed=true
    this.controller.abort()
    clearTimeout(this.timer)
    this.clearDeadlines?.()
    this.resume?.()
  }
  async connect() {
    while(!this.closed){
      try {
        const deadlines=new Map(this.resources.map(url=>[url,setTimeout(()=>{
          deadlines.delete(url)
          this.listeners.get('stream-error')?.({data:JSON.stringify({url,error:queryTimeout(url).message,status:504})})
        },500)]))
        this.clearDeadlines=()=>{for(const timer of deadlines.values())clearTimeout(timer);deadlines.clear()}
        const response=await request('/api/events',{
          method:'POST',headers:{'Content-Type':'application/json',Accept:'text/event-stream'},
          body:JSON.stringify({resources:this.resources}),signal:this.controller.signal,
        })
        if(!response.ok)throw Error(`HTTP ${response.status}: ${await response.text()}`)
        if(this.closed)return
        this.onopen?.()
        const reader=response.body.getReader(),decoder=new TextDecoder()
        let buffer=''
        while(!this.closed){
          const {value,done}=await reader.read()
          if(done)throw Error('Live stream ended')
          buffer+=decoder.decode(value,{stream:true})
          let boundary
          while((boundary=buffer.indexOf('\n\n'))>=0){
            const frame=buffer.slice(0,boundary);buffer=buffer.slice(boundary+2)
            const lines=frame.split('\n'),type=lines.find(line=>line.startsWith('event:'))?.slice(6).trim()
            const data=lines.filter(line=>line.startsWith('data:')).map(line=>line.slice(5).trimStart()).join('\n')
            if(type==='resource'||type==='stream-error'){
              const {url}=JSON.parse(data)
              clearTimeout(deadlines.get(url));deadlines.delete(url)
            }
            if(type)this.listeners.get(type)?.({data})
          }
        }
      } catch(error) {
        if(this.closed)return
        this.onerror?.(error)
      } finally {this.clearDeadlines?.()}
      await new Promise(resolve=>{this.resume=resolve;this.timer=setTimeout(resolve,1000)})
    }
  }
}
