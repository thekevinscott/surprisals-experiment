<script setup>
import {computed, nextTick, ref, watch} from 'vue'
import JsonContent from './JsonContent.vue'
const props=defineProps({text:String,selectedCase:Number})
const results=computed(()=>JSON.parse(props.text))
const root=ref(null)
watch([()=>props.text,()=>props.selectedCase],async()=>{
  await nextTick()
  const target=root.value?.querySelector(`[data-test-case="${props.selectedCase}"]`)
  target?.focus({preventScroll:true})
  target?.scrollIntoView({block:'start'})
},{immediate:true,flush:'post'})
</script>
<template>
  <div ref="root" class="test-cases">
    <section v-for="(test, position) in results.cases" :key="position" :data-test-case="position" :class="{selected:position===selectedCase}" tabindex="-1">
      <h3>Case {{ test.index }} · {{ test.status ?? (test.passed ? 'Passed' : 'Failed') }}</h3>
      <JsonContent :text="JSON.stringify(test)" />
    </section>
  </div>
</template>
<style scoped>
section { margin: 8px 0 16px; padding: 8px; border: 1px solid #d0dae7; border-radius: 6px; scroll-margin-top: 8px; }
.selected { outline: 2px solid #4169bb; }
h3 { margin: 0 0 8px; font-size: 12px; }
</style>
