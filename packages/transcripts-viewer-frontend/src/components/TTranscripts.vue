<script setup>
import ContentPanel from './ContentPanel.vue'
import TSample from './TSample.vue'
defineProps({ samples: Array })
</script>
<template>
  <ContentPanel v-if="samples.length" title="T samples" :summary="`${samples.length} samples`" :expanded="true" class="t-transcripts">
    <div class="sample-columns" :style="{ '--sample-count': samples.length }">
      <TSample v-for="sample in samples" :key="sample.id" :sample="sample" />
    </div>
    <p class="comparison-hint">Scroll horizontally to compare samples, or widen the fork.</p>
  </ContentPanel>
</template>
<style scoped>
.t-transcripts { margin-top: 8px; }
.sample-columns { display: grid; grid-template-columns: repeat(var(--sample-count), minmax(200px, 1fr)); gap: 8px; overflow-x: auto; }
.comparison-hint { margin: 6px 0 0; color: #657186; font-size: 10px; }
</style>
