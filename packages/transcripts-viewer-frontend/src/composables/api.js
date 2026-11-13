import {ref,watch} from 'vue'
import {watchData,hasLiveSnapshot,liveSnapshot} from './liveUpdates.js'
export {watchData}
export async function fetchJson(url,signal) {
  if(hasLiveSnapshot(url))return liveSnapshot(url)
  const response=await fetch(url,{signal})
  if(!response.ok)throw Error(`HTTP ${response.status}: ${await response.text()}`)
  return response.json()
}
export async function fetchText(url,signal) {
  if(hasLiveSnapshot(url))return liveSnapshot(url)
  const response=await fetch(url,{signal})
  if(!response.ok)throw Error(`HTTP ${response.status}: ${await response.text()}`)
  return response.text()
}
export function useLiveResource(sources,load) {
  const data=ref(null),loading=ref(false),error=ref('')
  watch(()=>JSON.stringify(sources()),(key,_,cleanup)=>{
    const urls=JSON.parse(key),controller=new AbortController()
    cleanup(()=>{controller.abort();data.value=null})
    data.value=null;error.value='';loading.value=urls.length>0
    if(!urls.length)return
    watchData(urls,signal=>load(signal,urls),{
      signal:controller.signal,
      onData:value=>{data.value=value;error.value='';loading.value=false},
      onError:e=>{error.value=e.message;loading.value=false},
    })
  },{immediate:true})
  return {data,loading,error}
}
