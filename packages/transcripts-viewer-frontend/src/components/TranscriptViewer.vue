<script setup>
import {provide} from 'vue'
import {fetchJson,fetchText,useLiveResource} from '../composables/api.js'
import {tTranscript} from '../composables/tTranscript.js'
import TranscriptView from './TranscriptView.vue'
const props=defineProps({source:String,url:String,files:Array,sourceUrl:Function})
provide('sourceUrl',props.sourceUrl)
const {data,loading,error}=useLiveResource(
  ()=>props.url?[props.url]:props.files.map(file=>file.url),
  async(signal,urls)=>{
    if(props.url)return (await fetchJson(urls[0],signal)).messages
    const contents=await Promise.all(urls.map(url=>fetchText(url,signal)))
    return contents.flatMap((text,index)=>tTranscript(text,props.files[index].source))
  },
)
</script>
<template>
  <p v-if="loading">Loading transcript…</p>
  <p v-else-if="error" role="alert">{{ error }}</p>
  <TranscriptView v-else-if="data" :messages="data" :source="source" />
</template>
