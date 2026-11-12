<script setup>
import {ref,watch,provide} from 'vue'
import FileContent from './FileContent.vue'
const props=defineProps({src:String,name:String,line:String})
provide('sourceUrl',(_path,line)=>{
  const viewer=new URL(location.href)
  viewer.hash=`files/${encodeURIComponent(props.name)}?${new URLSearchParams({src:props.src,...(line?{line:String(line)}:{})})}`
  return viewer.href
})
const text=ref(null),error=ref('')
watch(()=>props.src,async(_,__,cleanup)=>{
  const controller=new AbortController();cleanup(()=>controller.abort())
  text.value=null;error.value=''
  try{
    const response=await fetch(props.src,{signal:controller.signal})
    if(!response.ok)throw Error(`HTTP ${response.status}`)
    text.value=await response.text()
  }catch(e){if(!controller.signal.aborted)error.value=e.message}
},{immediate:true})
</script>
<template>
  <section class="file-viewer" aria-label="File viewer">
    <header><strong>{{ name }}</strong><a :href="src" target="_blank" rel="noopener">Open raw file ↗</a></header>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="text===null">Loading file…</p>
    <FileContent v-else :name="name" :text="text" :line="line" />
  </section>
</template>
<style scoped>
.file-viewer { background:white;padding:12px;border:1px solid #d0dae7;border-radius:6px; }
header { display:flex;justify-content:space-between;gap:16px;font-size:12px;overflow-wrap:anywhere;margin-bottom:12px; }
header a { flex-shrink:0; }
</style>
