<script setup>
import {inject} from 'vue'
import Button from 'primevue/button'
import {openTranscript} from '../composables/filePreview.js'
const props=defineProps({source:String,files:Array})
const rawUrl=inject('rawSourceUrl')
const sourceUrl=inject('sourceUrl')
function open() {
  const files=(props.source?[{source:props.source}]:(props.files??[])).map(file=>({...file,url:rawUrl(file.source)}))
  openTranscript({name:props.source??files[0]?.source??'Transcript',files,source:props.source,sourceUrl,
    rawFiles:props.source?[{source:props.source,url:rawUrl(props.source)}]:files})
}
</script>
<template>
  <Button text size="small" label="Open transcript" :disabled="!source && !files?.length" @click="open" />
</template>
