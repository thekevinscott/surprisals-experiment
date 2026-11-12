<script setup>
import ContentPanel from './ContentPanel.vue'
const files=['question.txt','input_output.json','solutions.json'].map(name=>({name,source:`problem/${name}`}))
</script>
<template><div class="problem-files"><ContentPanel v-for="file in files" :key="file.name" :source="file.source" :title="`File · ${file.name}`" :collapsible="false" /></div></template>
<style scoped>
.problem-files { display:grid;align-items:start;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-bottom:8px; }
@media(max-width:650px){.problem-files{grid-template-columns:1fr;}}
</style>
