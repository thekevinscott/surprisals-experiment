<script setup>
import {provide,ref} from 'vue'
import {useLiveResource,fetchText} from '../composables/api.js'
import FileContent from './FileContent.vue'
const raw=ref(false)
const props=defineProps({src:String,name:String,line:String,showName:{type:Boolean,default:true}})
provide('sourceUrl',(_path,line)=>{
  const viewer=new URL(location.href)
  viewer.hash=`files/${encodeURIComponent(props.name)}?${new URLSearchParams({src:props.src,...(line?{line:String(line)}:{})})}`
  return viewer.href
})
const {data:text,error}=useLiveResource(()=>[props.src],(signal,[url])=>fetchText(url,signal))
</script>
<template>
  <section class="file-viewer" aria-label="File viewer">
    <header><strong v-if="showName">{{ name }}</strong><button type="button" @click="raw=!raw">{{ raw ? 'Formatted view' : 'Raw view' }}</button></header>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="text===null">Loading file…</p>
    <pre v-else-if="raw" class="raw-file">{{ text }}</pre>
    <FileContent v-else :name="name" :text="text" :line="line" />
  </section>
</template>
<style scoped>
.file-viewer { background:white;padding:12px;border:1px solid #d0dae7;border-radius:6px; }
header { display:flex;justify-content:space-between;gap:16px;font-size:12px;overflow-wrap:anywhere;margin-bottom:12px; }
header button { flex-shrink:0; }
.raw-file { white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px; }
</style>
