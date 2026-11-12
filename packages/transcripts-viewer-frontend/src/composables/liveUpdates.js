// Multiplex every open resource over one SSE connection. Closed panels leave
// the subscription, and the server sends complete snapshots only when changed.
import {ref} from 'vue'
import {ResourceStream} from './resourceStream.js'
const subscribers=new Set(),snapshots=new Map()
export const connected=ref(true)
let stream,scheduled=false,current=''
export const liveSnapshot=url=>snapshots.get(url)
export const hasLiveSnapshot=url=>snapshots.has(url)
function reconcile(){
  scheduled=false
  const urls=[...new Set([...subscribers].flatMap(s=>s.urls))].sort()
  const key=JSON.stringify(urls)
  for(const url of snapshots.keys())if(!urls.includes(url))snapshots.delete(url)
  if(key===current)return
  current=key;stream?.close();stream=null
  if(!urls.length)return
  const next=new ResourceStream(urls);stream=next
  next.addEventListener('resource',event=>{
    if(stream!==next)return
    const {url,data}=JSON.parse(event.data)
    if(![...subscribers].some(subscriber=>subscriber.urls.includes(url)))return
    if(snapshots.has(url) && JSON.stringify(snapshots.get(url))===JSON.stringify(data))return
    snapshots.set(url,data)
    for(const subscriber of subscribers){
      if(subscriber.urls.includes(url)&&subscriber.urls.every(url=>snapshots.has(url)))subscriber.refresh()
    }
  })
  next.onopen=()=>{if(stream===next)connected.value=true}
  next.onerror=()=>{if(stream===next){snapshots.clear();connected.value=false}}
  next.addEventListener('stream-error',event=>{
    if(stream!==next)return
    const {url,error}=JSON.parse(event.data)
    snapshots.delete(url)
    for(const subscriber of subscribers)if(subscriber.urls.includes(url))subscriber.onError(Error(error))
  })
}
function schedule(){if(!scheduled){scheduled=true;queueMicrotask(reconcile)}}
export function watchData(urls,load,{signal,onData,onError}) {
  let running=false,dirty=false
  async function refresh(){
    dirty=true
    if(running||signal.aborted)return
    running=true
    try{
      while(dirty&&!signal.aborted){
        dirty=false
        try{const value=await load(signal);if(!signal.aborted)onData(value)}
        catch(error){if(!signal.aborted)onError(error)}
      }
    }finally{running=false}
  }
  const subscriber={urls,refresh,onError:error=>{if(!signal.aborted)onError(error)}}
  subscribers.add(subscriber);schedule()
  if(urls.every(url=>snapshots.has(url)))queueMicrotask(refresh)
  const stop=()=>{
    subscribers.delete(subscriber)
    for(const url of urls)if(![...subscribers].some(other=>other.urls.includes(url)))snapshots.delete(url)
    schedule()
  }
  signal.addEventListener('abort',stop,{once:true})
  if(signal.aborted)stop()
}
