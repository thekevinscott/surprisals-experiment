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
.file-tree .file-tree { padding-left:12px; }
.directory { display:block;padding:6px 4px 2px;color:#657186;font-size:11px; }
button { display:block;width:100%;border:0;border-radius:3px;background:none;color:#254c7f;text-align:left;padding:6px;font:inherit;font-size:12px;overflow-wrap:anywhere;cursor:pointer; }
button:hover,button[aria-current] { background:#e8eef8; }
</style>
