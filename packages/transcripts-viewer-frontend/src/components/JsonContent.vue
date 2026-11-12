<script setup>
import {computed} from 'vue'
import VueJsonPretty from 'vue-json-pretty'
import 'vue-json-pretty/lib/styles.css'
const props=defineProps({text:String})
const parsed=computed(()=>{
  try{return {value:JSON.parse(props.text)}}
  catch(error){return {error:error.message}}
})
</script>
<template>
  <div class="json-content">
    <template v-if="parsed.error"><p role="alert">Invalid JSON: {{ parsed.error }}</p><pre>{{ text }}</pre></template>
    <VueJsonPretty v-else :data="parsed.value" show-icon show-length show-line-number :editable="false" />
  </div>
</template>
<style scoped>
.json-content { min-width:0; overflow:auto; font-family:ui-monospace,monospace; font-size:12px; }
.json-content :deep(.vjs-tree) { font: inherit; }
.json-content :deep(.vjs-tree-node) { width: max-content; min-width: 100%; }
.json-content :deep(.vjs-value) { white-space: pre; word-break: normal; }
pre { white-space:pre; overflow-x:auto; font-family:inherit; }
</style>
