<script setup>
import {computed} from 'vue'
import {diffWordsWithSpace} from 'diff'
import {sliceTokens} from '../composables/adviceDiff.js'
import TokenText from './TokenText.vue'
const props=defineProps({text:String,tokens:Array,previous:String,previousTokens:Array})
const parts=computed(()=>{
  let before=0,after=0
  return diffWordsWithSpace(props.previous,props.text).map(part=>{
    const tokens=sliceTokens(part.removed?props.previousTokens:props.tokens,part.removed?before:after,part.value.length)
    if(!part.added)before+=part.value.length
    if(!part.removed)after+=part.value.length
    return {...part,tokens}
  })
})
</script>
<template><pre class="advice-diff"><span v-for="(part,i) in parts" :key="i" :class="{'diff-added':part.added,'diff-removed':part.removed}"><TokenText :text="part.value" :tokens="part.tokens" /></span></pre></template>
<style scoped>
.advice-diff { white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px; }
.diff-added { background:#bbf7d0; }
.diff-removed { background:#fecaca;text-decoration:line-through; }
.diff-added,.diff-removed { box-decoration-break:clone;-webkit-box-decoration-break:clone; }
.diff-added :deep(.scored-token),.diff-removed :deep(.scored-token) { background:transparent !important; }
</style>
