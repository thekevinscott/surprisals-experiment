<script setup>
import {computed,ref,watch} from 'vue'
import {fileTree} from '../composables/sampleFiles.js'
import FileViewer from './FileViewer.vue'
import FileTree from './FileTree.vue'
const props=defineProps({files:Array})
const selected=ref(props.files[0]?.source)
const active=computed(()=>props.files.find(file=>file.source===selected.value) ?? props.files[0])
const tree=computed(()=>fileTree(props.files))
watch(()=>props.files,()=>{selected.value=active.value?.source})
</script>
<template>
  <div class="files-viewer" :class="{'with-tree':files.length>1}">
    <nav v-if="files.length>1" aria-label="Files"><FileTree :nodes="tree" :selected="active?.source" @select="file=>selected=file.source" /></nav>
    <FileViewer v-if="active" :key="active.source" :src="active.url" :name="active.name" :show-name="files.length>1" />
    <p v-else>No written files recorded</p>
  </div>
</template>
<style scoped>
.files-viewer { display:grid;grid-template-columns:minmax(0,1fr);min-width:0;min-height:100%; }
.with-tree { grid-template-columns:minmax(120px,20%) minmax(0,1fr); }
nav { border-right:1px solid #d0dae7;padding-right:10px;margin-right:12px; }
.files-viewer :deep(.file-viewer) { border:0;padding:0;min-width:0; }
p { color:#657186;font-size:12px; }
</style>
