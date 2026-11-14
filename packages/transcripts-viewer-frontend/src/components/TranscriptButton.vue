<script setup>
import {computed,inject,ref,watch,nextTick} from 'vue'
import {useJsonQuery} from '../composables/queryState.js'
import Button from 'primevue/button'
import Popover from 'primevue/popover'
import {openTranscript} from '../composables/filePreview.js'
const props=defineProps({source:String,files:Array,modalTitle:String,turnMetadata:Object,turnSource:String,attemptCount:Number,label:{type:String,default:'Open transcript'}})
const uTurnContext=inject('uTurnContext',null)
const rawUrl=inject('rawSourceUrl')
const sourceUrl=inject('sourceUrl')
const picker=ref(null),anchor=ref(null)
const files=computed(()=>(props.source?[{source:props.source}]:(props.files??[])).map(file=>({...file,url:rawUrl(file.source)})))
const pickerOpen=useJsonQuery(()=>`picker:${files.value[0]?.source}`,false)
watch(pickerOpen,async value=>{await nextTick();if(value)picker.value?.show({currentTarget:anchor.value?.$el,target:anchor.value?.$el},anchor.value?.$el);else picker.value?.hide()},{immediate:true})
function openFile(file) {
  pickerOpen.value=false
  picker.value?.hide()
  const title=props.modalTitle ?? (props.source?'U transcript':'Transcript')
  const hash=props.turnMetadata?.u_request_sha256
  openTranscript({name:hash ? `${title} · u_request_sha256: ${hash}` : title,files:files.value,sourceUrl,turnMetadata:props.turnMetadata,uView:!!props.source,uNavigation:props.turnSource && uTurnContext ? ()=>uTurnContext(props.turnSource) : undefined},file)
}
function open(event) {
  if(files.value.length===1)openFile(files.value[0])
  else pickerOpen.value=!pickerOpen.value
}
</script>
<template>
  <Button ref="anchor" class="icon-button transcript-button" text size="small" aria-label="Open transcript" :title="attemptCount > 1 ? `Open transcript (${attemptCount} attempts)` : 'Open transcript'" :disabled="!files.length" @click="open"><span>{{ label }}</span><span v-if="attemptCount > 1" class="attempt-count">({{ attemptCount }})</span></Button>
  <Popover ref="picker" @hide="pickerOpen=false">
    <nav class="transcript-files" aria-label="Transcript files"><button v-for="file in files" :key="file.source" type="button" @click="openFile(file)">{{ file.source }}{{ file.timedOut ? ' (timed out)' : '' }}</button></nav>
  </Popover>
</template>
<style scoped>
.transcript-button { position:relative; }
.transcript-button:has(.attempt-count) { width:28px;min-width:28px;height:24px;padding-right:9px;padding-bottom:5px; }
.attempt-count { position:absolute;right:0;bottom:0;font-size:9px;line-height:11px;font-weight:600;background:var(--viewer-gray);border-radius:3px;padding:0 1px;pointer-events:none; }
.transcript-files { display:grid;max-width:min(640px,80vw);max-height:60vh;overflow:auto;gap:4px; }
.transcript-files button { border:0;border-radius:6px;background:var(--viewer-gray);padding:8px;text-align:left;overflow-wrap:anywhere;font-size:12px;color:inherit;cursor:pointer; }
</style>
