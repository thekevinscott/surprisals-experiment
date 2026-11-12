<script setup>
import {provide} from 'vue'
import {fetchText,useLiveResource} from '../composables/api.js'
import {transcriptFile} from '../composables/transcriptFile.js'
import TranscriptView from './TranscriptView.vue'
const props=defineProps({source:String,files:Array,sourceUrl:Function})
provide('sourceUrl',props.sourceUrl)
const {data,loading,error}=useLiveResource(
  ()=>props.files.map(file=>file.url),
  async(signal,urls)=>{
    const contents=await Promise.all(urls.map(url=>fetchText(url,signal)))
    return contents.flatMap((text,index)=>transcriptFile(text,props.files[index].source))
  },
)
</script>
<template>
  <p v-if="loading">Loading transcript…</p>
  <p v-else-if="error" role="alert">{{ error }}</p>
  <TranscriptView v-else-if="data" content-only :messages="data" :source="source" />
</template>
