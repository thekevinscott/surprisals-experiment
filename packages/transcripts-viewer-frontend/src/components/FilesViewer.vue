<script setup>
import {computed,ref,watch} from 'vue'
import {selectPreviewFile} from '../composables/filePreview.js'
import {fileTree} from '../composables/sampleFiles.js'
import FileViewer from './FileViewer.vue'
import FileTree from './FileTree.vue'
const props=defineProps({files:Array})
const selected=ref(props.files[0]?.source)
const active=computed(()=>props.files.find(file=>file.source===selected.value) ?? props.files[0])
const tree=computed(()=>fileTree(props.files))
watch(()=>props.files,()=>{selected.value=active.value?.source})
watch(active,file=>selectPreviewFile(file),{immediate:true})
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
nav { position:sticky;top:0;align-self:start;max-height:calc(100dvh - 100px);overflow:auto;border-right:1px solid var(--viewer-border);padding-right:8px;margin-right:8px; }
p { color:var(--viewer-muted);font-size:12px; }
</style>
