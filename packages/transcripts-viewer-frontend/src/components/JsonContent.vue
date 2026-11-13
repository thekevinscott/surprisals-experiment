<script setup>
import {computed,inject,ref,watch,nextTick} from 'vue'
import {useUrlState} from '../composables/urlState.js'
import VueJsonPretty from 'vue-json-pretty'
import 'vue-json-pretty/lib/styles.css'
const props=defineProps({text:String})
const scope=inject('viewStateKey',()=> 'json'),testCase=inject('testCase',()=>null)
const collapsed=useUrlState(()=>`json:${scope()}:collapsed`,[])
const selected=useUrlState(()=>`json:${scope()}:selected`,()=>testCase()!=null?`root.cases[${testCase()}]`:'')
const element=ref(null)
function collapse(value,node) {
  const paths=new Set(collapsed.value)
  if(value)paths.add(node.path);else paths.delete(node.path)
  collapsed.value=[...paths].sort()
}
watch(selected,async()=>{await nextTick();element.value?.querySelector('.is-highlight')?.scrollIntoView({block:'center'})},{immediate:true,flush:'post'})
const parsed=computed(()=>{
  try{return {value:JSON.parse(props.text)}}
  catch(error){return {error:error.message}}
})
</script>
<template>
  <div ref="element" class="json-content">
    <template v-if="parsed.error"><p role="alert">Invalid JSON: {{ parsed.error }}</p><pre>{{ text }}</pre></template>
    <VueJsonPretty v-else :key="JSON.stringify(collapsed)" :path-collapsible="node=>collapsed.includes(node.path)" @icon-click="collapse" @brackets-click="collapse" :selected-value="selected" @node-click="node=>selected=node.path" highlight-selected-node :data="parsed.value" show-icon show-length show-line-number :editable="false" />
  </div>
</template>
<style scoped>
.json-content { min-width:0; overflow:auto; font-family:ui-monospace,monospace; font-size:12px; }
.json-content :deep(.vjs-tree) { font: inherit; }
.json-content :deep(.vjs-tree-node) { width: max-content; min-width: 100%; }
.json-content :deep(.vjs-value) { white-space: pre; word-break: normal; }
pre { white-space:pre; overflow-x:auto; font-family:inherit; }
</style>
