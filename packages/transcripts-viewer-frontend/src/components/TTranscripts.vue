<script setup>
import {inject} from 'vue'
import {sampleColumnCount} from '../composables/sampleFiles.js'
import TSample from './TSample.vue'
defineProps({ samples: Array })
const configuredCount=inject('sampleCount',()=>null)
</script>
<template>
  <div v-if="samples.length" class="t-transcripts">
    <div class="sample-columns" :style="{ '--sample-count': sampleColumnCount(configuredCount(),samples.length) }">
      <TSample v-for="sample in samples" :key="sample.id" :sample="sample" />
    </div>
  </div>
</template>
<style scoped>
.sample-columns { display: grid; grid-template-columns: repeat(var(--sample-count), minmax(56px, 1fr)); gap: 4px; }
</style>
