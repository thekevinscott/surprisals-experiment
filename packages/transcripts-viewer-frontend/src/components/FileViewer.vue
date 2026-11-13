<script setup>
import {computed,provide,ref,watch} from 'vue'
import {useLiveResource,fetchText} from '../composables/api.js'
import FileContent from './FileContent.vue'
import {addedRanges} from '../composables/adviceDiff.js'
import AdviceDiff from './AdviceDiff.vue'
import TokenText from './TokenText.vue'
const props=defineProps({showDiff:Boolean,comparisonText:String,comparisonTokens:Array,previousText:String,highlightId:Number,src:String,name:String,line:String,initialText:String,tokens:Array,measurement:String,testCase:Number,showName:{type:Boolean,default:true}})
provide('viewStateKey',()=>props.src)
provide('testCase',()=>props.testCase)
provide('disclosurePath',()=>props.src)
provide('sourceUrl',(_path,line)=>{
  const viewer=new URL(location.href)
  viewer.hash=`files/${encodeURIComponent(props.name)}?${new URLSearchParams({src:props.src,...(line?{line:String(line)}:{})})}`
  return viewer.href
})
const {data:liveText,error}=useLiveResource(()=>[props.src],(signal,[url])=>fetchText(url,signal))
const suppressFade=ref(false)
watch(()=>props.showDiff,()=>{suppressFade.value=true})
watch(()=>props.highlightId,()=>{suppressFade.value=false})
const additions=computed(()=>suppressFade.value||props.previousText==null?[]:addedRanges(props.previousText,text.value??''))
const text=computed(()=>liveText.value ?? props.initialText ?? null)
</script>
<template>
  <section class="file-viewer" aria-label="File viewer">
    <header v-if="showName"><strong>{{ name }}</strong></header>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="text===null">Loading file…</p>
    <AdviceDiff v-else-if="showDiff && comparisonText!=null" :text="text" :tokens="tokens" :previous="comparisonText" :previous-tokens="comparisonTokens" />
    <AdviceDiff v-else-if="previousText!=null && !suppressFade" :key="highlightId" fading :text="text" :tokens="tokens" :previous="previousText" />
    <template v-else-if="tokens || previousText!=null">
      <p>{{ measurement }}</p>
      <pre class="raw-file"><TokenText :key="highlightId" :additions="additions" :text="text" :tokens="tokens" /></pre>
    </template>
    <FileContent v-else :name="name" :text="text" :line="line" />
  </section>
</template>
<style scoped>
.file-viewer { min-width:0; }
header { display:flex;justify-content:space-between;gap:16px;font-size:12px;overflow-wrap:anywhere;margin-bottom:8px; }
.raw-file { white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px; }
</style>
