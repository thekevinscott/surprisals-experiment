<script setup>
import {computed,provide} from 'vue'
import {useLiveResource,fetchText} from '../composables/api.js'
import FileContent from './FileContent.vue'
import TokenText from './TokenText.vue'
const props=defineProps({src:String,name:String,line:String,initialText:String,tokens:Array,measurement:String,showName:{type:Boolean,default:true}})
provide('sourceUrl',(_path,line)=>{
  const viewer=new URL(location.href)
  viewer.hash=`files/${encodeURIComponent(props.name)}?${new URLSearchParams({src:props.src,...(line?{line:String(line)}:{})})}`
  return viewer.href
})
const {data:liveText,error}=useLiveResource(()=>[props.src],(signal,[url])=>fetchText(url,signal))
const text=computed(()=>liveText.value ?? props.initialText ?? null)
</script>
<template>
  <section class="file-viewer" aria-label="File viewer">
    <header v-if="showName"><strong>{{ name }}</strong></header>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="text===null">Loading file…</p>
    <template v-else-if="tokens">
      <p>{{ measurement }}</p>
      <pre class="raw-file"><TokenText :text="text" :tokens="tokens" /></pre>
    </template>
    <FileContent v-else :name="name" :text="text" :line="line" />
  </section>
</template>
<style scoped>
.file-viewer { background:white;padding:12px;border:1px solid #d0dae7;border-radius:6px; }
header { display:flex;justify-content:space-between;gap:16px;font-size:12px;overflow-wrap:anywhere;margin-bottom:12px; }
.raw-file { white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px; }
</style>
