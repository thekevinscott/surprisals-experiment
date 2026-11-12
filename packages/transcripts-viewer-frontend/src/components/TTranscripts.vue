<script setup>
import ContentPanel from './ContentPanel.vue'
import TSample from './TSample.vue'
defineProps({ samples: Array })
</script>
<template>
  <ContentPanel v-if="samples.length" title="T samples" :summary="`${samples.length} samples`" preview :collapsible="samples.length > 1" class="t-transcripts" v-slot="{ expanded }">
    <div class="sample-columns" :style="{ '--sample-count': expanded ? samples.length : 1 }">
      <TSample v-for="sample in samples" :key="sample.id" :sample="sample" />
    </div>
    <p class="comparison-hint">{{ expanded ? 'Scroll horizontally to compare samples, or widen the fork.' : 'Expand to compare T samples side by side.' }}</p>
  </ContentPanel>
</template>
<style scoped>
.t-transcripts { margin-top: 8px; }
.sample-columns { display: grid; grid-template-columns: repeat(var(--sample-count), minmax(200px, 1fr)); gap: 8px; overflow-x: auto; }
.comparison-hint { margin: 6px 0 0; color: #657186; font-size: 10px; }
</style>
