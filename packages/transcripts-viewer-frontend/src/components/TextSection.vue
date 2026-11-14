<script setup>
import ContentPanel from './ContentPanel.vue'
defineProps({label:String,text:String,stateKey:String})
</script>
<template>
  <ContentPanel sticky-header class="text-section" :title="label" :state-key="stateKey" :expanded="true">
    <p>{{ text }}</p>
  </ContentPanel>
</template>
<style scoped>
.text-section { margin-top: 4px; }
p { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font-family: ui-monospace,monospace; font-size: 12px; line-height: 1.5; }
</style>
