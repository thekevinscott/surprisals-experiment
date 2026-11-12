<script setup>
import {computed, inject} from 'vue'
import {openFile} from '../composables/filePreview.js'
import {passBlocks, testCaseBlocks} from '../composables/outcomes.js'
const props=defineProps({passed: Number, total: Number, cases: Array, source: String, unit: {type: String, default: 'tests'}})
const sourceUrl=inject('sourceUrl',()=>undefined)
const blocks=computed(()=>props.cases ? testCaseBlocks(props.cases) : passBlocks(props.passed,props.total).map(outcome=>({outcome})))
const target=computed(()=>props.source && sourceUrl(props.source))
const clickable=computed(()=>!!props.cases && !!target.value)
function openCase(position) { openFile(target.value,{testCase:position}) }
</script>
<template>
  <span class="pass-blocks" :role="clickable ? 'group' : 'img'" :aria-label="`${passed}/${total} ${unit} passed`" :title="`${passed}/${total} ${unit} passed`">
    <template v-for="(block, index) in blocks" :key="index">
      <button v-if="clickable" type="button" class="pass-block" :class="block.outcome" :aria-label="`Case ${block.index}: ${block.outcome}. Open test results`" :title="`Case ${block.index}: ${block.outcome}`" @click.stop="openCase(block.position)"></button>
      <span v-else class="pass-block" :class="block.outcome" aria-hidden="true"></span>
    </template>
  </span>
</template>
<style scoped>
.pass-blocks { display: inline-flex; flex-wrap: nowrap; gap: 0; max-width: 100%; min-width: 0; vertical-align: middle; }
.pass-block { flex: 0 1 8px; width: 8px; min-width: 0; height: 8px; border-radius: 0; border: 0; padding: 0; }
button.pass-block { cursor: pointer; }
button.pass-block:focus-visible { outline: 2px solid #254c7f; outline-offset: 2px; }
.passed { background: #15803d; }
.failed { background: #b91c1c; }
</style>
