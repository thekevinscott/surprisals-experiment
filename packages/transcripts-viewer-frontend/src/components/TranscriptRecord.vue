<script setup>
import {computed} from 'vue'
import TextSection from './TextSection.vue'
const props=defineProps({label:String,message:Object,stateKey:String,uView:Boolean})
const record=computed(()=>{
  if(!props.uView)return null
  try{return JSON.parse(props.message.raw)}catch{return null}
})
</script>
<template>
  <div v-if="record">
    <TextSection v-if="record.role==='assistant' && record.reasoning" data-part="reasoning" :label="`${label} · reasoning`" :state-key="`${stateKey}/reasoning`" :text="record.reasoning" />
    <TextSection data-part="content" :label="`${label} · ${record.role}`" :state-key="stateKey" :text="record.content" />
  </div>
  <TextSection v-else :label="label" :state-key="stateKey" :text="message.raw" />
</template>
