<script setup>
import {computed,inject,ref} from 'vue'
import {fetchJson,fetchText,useLiveResource} from '../composables/api.js'
import {tTranscript} from '../composables/tTranscript.js'
import ContentPanel from './ContentPanel.vue'
import TranscriptView from './TranscriptView.vue'
const props=defineProps({source:String,url:String,files:Array})
const rawUrl=inject('rawSourceUrl')
const displaySource=computed(()=>props.source ?? (props.files?.length===1 ? props.files[0].source : undefined))
const expanded=ref(false)
const {data,loading,error}=useLiveResource(
  ()=>expanded.value ? (props.url?[props.url]:(props.files??[]).map(file=>rawUrl(file.source))) : [],
  async(signal,urls)=>{
    if(props.url)return (await fetchJson(urls[0],signal)).messages
    const contents=await Promise.all(urls.map(url=>fetchText(url,signal)))
    return contents.flatMap((text,index)=>tTranscript(text,props.files[index].source))
  },
)
</script>
<template>
  <ContentPanel local v-model:expanded="expanded" title="Transcript" :source="displaySource">
    <template v-if="expanded">
      <p v-if="loading">Loading transcript…</p><p v-else-if="error" role="alert">{{ error }}</p>
      <TranscriptView v-else-if="data" :messages="data" :source="displaySource" />
    </template>
  </ContentPanel>
</template>
