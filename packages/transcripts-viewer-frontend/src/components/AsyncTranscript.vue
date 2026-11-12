<script setup>
import {computed,inject,ref} from 'vue'
import {fetchJson,useLazyResource} from '../composables/api.js'
import {tTranscript} from '../composables/tTranscript.js'
import ContentPanel from './ContentPanel.vue'
import TranscriptView from './TranscriptView.vue'
const props=defineProps({source:String,url:String,files:Array})
const rawUrl=inject('rawSourceUrl')
const displaySource=computed(()=>props.source ?? (props.files?.length===1 ? props.files[0].source : undefined))
const expanded=ref(false)
const {data,loading,error}=useLazyResource(expanded,async signal=>{
  if(props.url)return (await fetchJson(props.url,signal)).messages
  const messages=[]
  for(const file of props.files){
    const response=await fetch(rawUrl(file.source),{signal})
    if(!response.ok)throw Error(`HTTP ${response.status}`)
    messages.push(...tTranscript(await response.text(),file.source))
  }
  return messages
})
</script>
<template>
  <ContentPanel local v-model:expanded="expanded" title="Transcript" :source="displaySource">
    <template v-if="expanded">
      <p v-if="loading">Loading transcript…</p><p v-else-if="error" role="alert">{{ error }}</p>
      <TranscriptView v-else-if="data" :messages="data" :source="displaySource" />
    </template>
  </ContentPanel>
</template>
