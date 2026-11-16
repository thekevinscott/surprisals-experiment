<script setup>
import {computed,provide,watch,ref} from 'vue'
import {fetchJson,useLiveResource,watchData} from '../composables/api.js'
import {transcriptMetadataUrl,transcriptBlocks,observeTranscriptBlocks} from '../composables/lazyTranscript.js'
import TranscriptView from './TranscriptView.vue'
const props=defineProps({source:String,files:Array,sourceUrl:Function,turnMetadata:Object,uView:Boolean})
provide('sourceUrl',props.sourceUrl)
provide('disclosurePath',()=>props.files[0].source)
const hasReply=ref(false)
const {data,loading,error}=useLiveResource(
  ()=>[props.turnMetadata?.u_messages==null?transcriptMetadataUrl(props.files[0].url):props.files[0].url.replace('/files/',`/transcript-context/${props.turnMetadata.u_messages}/`)],
  async(signal,urls)=>{
    const metadata=await fetchJson(urls[0],signal)
    hasReply.value=metadata.hasReply??false
    return transcriptBlocks(metadata,props.files[0].source,props.files[0].url,data.value ?? [])
  },
)
const turnError=computed(()=>{
  if(props.files[0].error)return props.files[0].error
  return hasReply.value ? null : props.turnMetadata?.error
})
let blocks
watch(data,(messages,_,cleanup)=>{
  blocks=undefined
  if(!messages)return
  blocks=observeTranscriptBlocks(messages,(url,receive)=>{
    const controller=new AbortController()
    watchData([url],signal=>fetchJson(url,signal),{
      signal:controller.signal,onData:receive,onError:failure=>{error.value=failure.message},
    })
    return ()=>controller.abort()
  })
  const current=blocks
  cleanup(()=>current.dispose())
},{flush:'sync'})
</script>
<template>
  <p v-if="loading">Loading transcript…</p>
  <p v-if="error" role="alert">{{ error }}</p>
  <TranscriptView v-if="data" :u-view="uView" lazy :messages="data" :source="source" @visible="(index,visible)=>blocks?.visible(index,visible)" />
  <p v-if="turnError" class="turn-error" role="status">{{ turnError }}</p>
</template>
<style scoped>
.turn-error { white-space:pre-wrap;overflow-wrap:anywhere; }
</style>
