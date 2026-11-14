<script setup>
defineProps({nodes:Array,selected:String})
defineEmits(['select'])
</script>
<template>
  <ul class="file-tree">
    <li v-for="node in nodes" :key="node.file?.source ?? node.name">
      <template v-if="node.children"><span class="directory">{{ node.name }}</span><FileTree :nodes="node.children" :selected="selected" @select="$emit('select',$event)" /></template>
      <button v-else type="button" :aria-current="selected===node.file.source?'true':undefined" @click="$emit('select',node.file)">{{ node.name }}</button>
    </li>
  </ul>
</template>
<style scoped>
.file-tree { list-style:none;padding:0;margin:0; }
.file-tree .file-tree { padding-left:16px; }
.directory { display:block;padding:4px 4px 2px;color:var(--viewer-muted);font-size:12px; }
button { display:block;width:100%;border:0;border-radius:6px;background:none;color:var(--viewer-link);text-align:left;padding:4px;font:inherit;font-size:12px;overflow-wrap:anywhere;cursor:pointer; }
button:hover,button[aria-current] { background:var(--viewer-gray); }
</style>
