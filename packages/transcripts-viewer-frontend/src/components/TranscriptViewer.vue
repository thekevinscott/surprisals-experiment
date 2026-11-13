<script setup>
import {computed,provide,watch} from 'vue'
import {fetchJson,useLiveResource,watchData} from '../composables/api.js'
import {transcriptMetadataUrl,transcriptBlocks,observeTranscriptBlocks} from '../composables/lazyTranscript.js'
import TranscriptView from './TranscriptView.vue'
const props=defineProps({source:String,files:Array,sourceUrl:Function,turnMetadata:Object})
provide('sourceUrl',props.sourceUrl)
const {data,loading,error}=useLiveResource(
  ()=>[transcriptMetadataUrl(props.files[0].url)],
  async(signal,urls)=>{
    const metadata=await fetchJson(urls[0],signal)
    const count=props.turnMetadata?.u_messages
    const requestMetadata=count == null ? metadata : {...metadata,blocks:metadata.blocks.slice(0,count+(metadata.blocks[count]?.type==='assistant' ? 1 : 0))}
    return transcriptBlocks(requestMetadata,props.files[0].source,props.files[0].url,data.value ?? [])
  },
)
const turnError=computed(()=>{
  const count=props.turnMetadata?.u_messages
  const hasReply=count != null && data.value?.some(message=>message.index===count && message.role==='assistant')
  return hasReply ? null : props.turnMetadata?.error
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
  <TranscriptView v-if="data" lazy :messages="data" :source="source" @visible="(index,visible)=>blocks?.visible(index,visible)" />
  <p v-if="turnError" class="turn-error" role="status">{{ turnError }}</p>
</template>
<style scoped>
.turn-error { white-space:pre-wrap;overflow-wrap:anywhere; }
</style>
