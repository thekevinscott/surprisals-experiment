<script setup>
import {computed} from 'vue'
import PythonCode from './PythonCode.vue'
import JsonContent from './JsonContent.vue'
const props=defineProps({text:String})
const solutions=computed(()=>{
  try {const value=JSON.parse(props.text);return Array.isArray(value)&&value.every(s=>typeof s==='string')?value:null}
  catch{return null}
})
</script>
<template>
  <div v-if="solutions" class="solutions">
    <section v-for="(solution,index) in solutions" :key="index"><h4>Solution {{ index+1 }}</h4><PythonCode :text="solution" /></section>
    <p v-if="!solutions.length">No solutions recorded.</p>
  </div>
  <JsonContent v-else :text="text" />
</template>
<style scoped>
h4 { margin:0 0 6px;font-size:12px; }
section+section { margin-top:12px; }

</style>
