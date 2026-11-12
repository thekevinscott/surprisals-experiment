<script setup>
import {inject,ref,onBeforeUnmount} from 'vue'
import {openFile} from '../composables/filePreview.js'
import Button from 'primevue/button'
import Popover from 'primevue/popover'
import VueJsonPretty from 'vue-json-pretty'
import 'vue-json-pretty/lib/styles.css'
const props=defineProps({title:String,metadata:Object,source:String,sourceLine:Number})
const sourceUrl=inject('sourceUrl',()=>undefined)
const popup=ref(null),mode=ref('source'),pinned=ref(false)
let timer
function show(event,value){clearTimeout(timer);mode.value=value;popup.value.show(event)}
function leave(){timer=setTimeout(()=>{if(!pinned.value)popup.value?.hide()},150)}
function pin(event){if(pinned.value){popup.value.hide();pinned.value=false}else{pinned.value=true;show(event,'metadata')}}
onBeforeUnmount(()=>clearTimeout(timer))
</script>
<template>
  <span class="source-actions">
    <Button class="icon-button" v-if="metadata != null" text rounded size="small" label="ⓘ" :aria-label="`Metadata for ${title}`" @mouseenter="show($event,'metadata')" @mouseleave="leave" @focus="show($event,'metadata')" @click.stop="pin" />
    <Button class="icon-button" v-if="source && sourceUrl(source,sourceLine)" as="a" text rounded size="small" label="📄" aria-label="Source file" :href="sourceUrl(source,sourceLine)" @mouseenter="show($event,'source')" @mouseleave="leave" @focus="show($event,'source')" @click.prevent.stop="popup?.hide();openFile(sourceUrl(source,sourceLine))" />
    <Popover ref="popup" @hide="pinned=false" @mouseenter="clearTimeout(timer)" @mouseleave="leave" :style="{maxWidth:'min(500px, 95vw)',maxHeight:'60vh',overflow:'auto'}">
      <strong>{{ mode === 'metadata' ? `Metadata for ${title}` : 'Source file' }}</strong>
      <VueJsonPretty v-if="mode === 'metadata'" :data="metadata" :deep="2" show-icon />
      <pre v-else>{{ source }}</pre>
    </Popover>
  </span>
</template>
<style scoped>
.source-actions { display:inline-flex; align-items:center; gap:2px; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; font-size:11px; }
</style>
