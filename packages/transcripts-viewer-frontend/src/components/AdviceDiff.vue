<script setup>
import {computed,ref} from 'vue'
import {diffWordsWithSpace} from 'diff'
import {sliceTokens} from '../composables/adviceDiff.js'
import TokenText from './TokenText.vue'
const props=defineProps({fading:Boolean,text:String,tokens:Array,previous:String,previousTokens:Array})
const expired=ref(false)
function measure(element) {
  if(element&&!element.style.getPropertyValue('--deleted-width'))element.style.setProperty('--deleted-width',`${element.getBoundingClientRect().width}px`)
}
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
<template><pre class="advice-diff" :class="{'fading-diff':fading}"><template v-for="(part,i) in parts" :key="i"><template v-if="fading && part.removed"><span v-if="!expired" class="deleted-run"><span v-for="(word,j) in part.value.match(/\s+|[^\s]+/g)" :key="j" :ref="measure" class="advice-deleted" @animationend="expired=true">{{ word }}</span></span></template><span v-else :class="{'diff-added':part.added,'advice-added':part.added&&fading,'diff-removed':part.removed}"><TokenText :text="part.value" :tokens="part.tokens" /></span></template></pre></template>
<style scoped>
.advice-diff { white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px; }
.advice-added { animation:added-fade 3s ease 1s forwards; }
.advice-deleted { display:inline-block;vertical-align:bottom;white-space:pre;overflow:hidden;background:var(--viewer-removed);animation:deleted-fade 3s ease 1s forwards; }
@keyframes added-fade { to { background-color:transparent; } }
@keyframes deleted-fade { from { max-width:var(--deleted-width);opacity:1; } to { max-width:0;opacity:0; } }
.diff-added { background:var(--viewer-added); }
.diff-removed { background:var(--viewer-removed);text-decoration:line-through; }
.diff-added,.diff-removed { box-decoration-break:clone;-webkit-box-decoration-break:clone; }
.diff-added :deep(.scored-token),.diff-removed :deep(.scored-token) { background:transparent !important; }
</style>
