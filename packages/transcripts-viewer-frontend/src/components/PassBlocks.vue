<script setup>
import {computed, inject} from 'vue'
import {openFile} from '../composables/filePreview.js'
import {testCaseBlocks} from '../composables/outcomes.js'
const props=defineProps({passed: Number, total: Number, cases: Array, source: String, unit: {type: String, default: 'tests'}})
const sourceUrl=inject('sourceUrl',()=>undefined)
const blocks=computed(()=>testCaseBlocks(props.cases))
const target=computed(()=>props.source && sourceUrl(props.source))
const clickable=computed(()=>!!props.cases && !!target.value)
function openCase(index) { openFile(target.value,{testCase:index}) }
</script>
<template>
  <span class="pass-blocks" :style="{'--test-count':blocks.length,'--gap-count':Math.max(1,blocks.length-1)}" :role="clickable ? 'group' : 'img'" :aria-label="`${passed}/${total} ${unit} passed`" :title="`${passed}/${total} ${unit} passed`">
    <template v-for="(block, index) in blocks" :key="index">
      <button v-if="clickable" type="button" class="pass-block" :data-status="block.status" :aria-label="`Case ${block.index}: ${block.status ?? ''}. Open test results`" :title="JSON.stringify(cases[index],null,2)" @click.stop="openCase(index)"></button>
      <span v-else class="pass-block" :data-status="block.status" aria-hidden="true"></span>
    </template>
  </span>
</template>
<style scoped>
.pass-blocks { display: inline-flex; flex-wrap: nowrap; justify-content: center; width: 100%; gap: clamp(0px, calc((100% - var(--test-count) * 8px) / var(--gap-count)), 3px); max-width: 100%; min-width: 0; vertical-align: middle; }
.pass-block { flex: 0 1 8px; width: 8px; min-width: 0; height: 8px; border-radius: 0; border: 0; padding: 0; }
button.pass-block { cursor: pointer; }
button.pass-block:focus-visible { outline: 2px solid #254c7f; outline-offset: 2px; }
.pass-block { background:var(--viewer-muted); }
.pass-block[data-status="passed"] { background:var(--viewer-pass); }
.pass-block[data-status]:not([data-status="passed"]) { background:var(--viewer-fail); }
</style>
