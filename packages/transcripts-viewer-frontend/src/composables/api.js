import {ref,watch} from 'vue'
export async function fetchJson(url, signal) {
  const response=await fetch(url,{signal})
  if(!response.ok)throw Error(`HTTP ${response.status}: ${await response.text()}`)
  return response.json()
}
export function useLazyResource(expanded, load) {
  const data=ref(null),loading=ref(false),error=ref('')
  watch(expanded,async (open,_,onCleanup)=>{
    if(!open)return
    const controller=new AbortController()
    onCleanup(()=>controller.abort())
    loading.value=true;error.value='';data.value=null
    try {data.value=await load(controller.signal)}
    catch(e){if(!controller.signal.aborted)error.value=e.message}
    finally{if(!controller.signal.aborted)loading.value=false}
  })
  return {data,loading,error}
}
