<script setup>
import {computed,inject} from 'vue'
import {useUrlState} from '../composables/urlState.js'
import JsonContent from './JsonContent.vue'
import {transcriptLines} from '../composables/transcriptFile.js'
import SearchSelect from './SearchSelect.vue'
const props=defineProps({text:String,line:String})
const lines=computed(()=>transcriptLines(props.text).map((raw,index)=>({raw,number:index+1})))
const options=computed(()=>lines.value.map(line=>({value:`Line ${line.number}`,description:line.raw})))
const scope=inject('viewStateKey',()=> 'jsonl')
const selected=useUrlState(()=>`file:${scope()}:record`,()=>options.value.find(option=>option.value===`Line ${props.line}`)?.value??options.value[0]?.value??'')
const active=computed(()=>lines.value[options.value.findIndex(option=>option.value===selected.value)])
function step(offset){const index=options.value.findIndex(option=>option.value===selected.value);selected.value=options.value[index+offset]?.value??selected.value}
</script>
<template>
  <template v-if="active">
    <div class="file-controls">
      <SearchSelect label="Block" :model-value="selected" :options="options" @update:model-value="selected=$event" />
      <button :disabled="active===lines[0]" @click="step(-1)" aria-label="Previous record">←</button>
      <button :disabled="active===lines.at(-1)" @click="step(1)" aria-label="Next record">→</button>
      <span>{{ lines.length }} records</span>
    </div>
    <pre v-if="!active.raw.trim()">{{ active.raw }}</pre>
    <JsonContent v-else :key="selected" :text="active.raw" />
  </template>
  <p v-else>Empty JSONL file.</p>
</template>
<style scoped>
.file-controls { display:flex;gap:8px;align-items:end;margin:12px 0;font-size:12px; }
.file-controls :deep(.search-select){width:min(500px,65vw);}
button { padding:6px 10px;cursor:pointer; }
</style>
