<script setup>
import {inject,ref,onBeforeUnmount,watch,nextTick,provide} from 'vue'
import {useUrlState} from '../composables/urlState.js'
import JsonContent from './JsonContent.vue'
import {openFile} from '../composables/filePreview.js'
import Button from 'primevue/button'
import Popover from 'primevue/popover'
const props=defineProps({stateKey:String,title:String,metadata:Object,source:String,sourceLine:Number})
const sourceUrl=inject('sourceUrl',()=>undefined)
const popup=ref(null),anchor=ref(null),mode=ref('source')
const pinned=useUrlState(()=>`metadata:${props.stateKey}`,false)
provide('viewStateKey',()=>`metadata:${props.stateKey}`)
watch(pinned,async value=>{await nextTick();if(value){mode.value='metadata';popup.value?.show({currentTarget:anchor.value?.$el,target:anchor.value?.$el},anchor.value?.$el)}else popup.value?.hide()},{immediate:true})
let timer
function show(event,value){clearTimeout(timer);mode.value=value;popup.value.show(event)}
function leave(){timer=setTimeout(()=>{if(!pinned.value)popup.value?.hide()},150)}
function pin(){pinned.value=!pinned.value}
onBeforeUnmount(()=>clearTimeout(timer))
</script>
<template>
  <span class="source-actions">
    <Button ref="anchor" class="icon-button" v-if="metadata != null" text rounded size="small" label="ⓘ" :aria-label="`Metadata for ${title}`" @mouseenter="show($event,'metadata')" @mouseleave="leave" @focus="show($event,'metadata')" @click.stop="pin" />
    <Button class="icon-button" v-if="source && sourceUrl(source,sourceLine)" as="a" text rounded size="small" label="📄" aria-label="Source file" :href="sourceUrl(source,sourceLine)" @mouseenter="show($event,'source')" @mouseleave="leave" @focus="show($event,'source')" @click.prevent.stop="popup?.hide();openFile(sourceUrl(source,sourceLine))" />
    <Popover ref="popup" @hide="pinned=false" @mouseenter="clearTimeout(timer)" @mouseleave="leave" :style="{maxWidth:'min(500px, 95vw)',maxHeight:'60vh',overflow:'auto'}">
      <strong>{{ mode === 'metadata' ? `Metadata for ${title}` : 'Source file' }}</strong>
      <JsonContent v-if="mode === 'metadata'" :text="JSON.stringify(metadata)" />
      <pre v-else>{{ source }}</pre>
    </Popover>
  </span>
</template>
<style scoped>
.source-actions { display:inline-flex; align-items:center; gap:2px; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; font-size:12px; }
</style>
