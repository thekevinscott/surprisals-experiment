<script setup>
import TextSection from './TextSection.vue'
defineProps({label:String,message:Object,stateKey:String})
</script>
<template>
  <TextSection :label="label" :state-key="stateKey" :source="message.source" :source-line="message.line" :text="message.raw" />
</template>
