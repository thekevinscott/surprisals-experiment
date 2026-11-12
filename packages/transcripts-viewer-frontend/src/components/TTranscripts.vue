<script setup>
import TSample from './TSample.vue'
defineProps({ samples: Array })
</script>
<template>
  <div v-if="samples.length" class="t-transcripts">
    <div class="sample-columns" :style="{ '--sample-count': samples.length }">
      <TSample v-for="sample in samples" :key="sample.id" :sample="sample" />
    </div>
  </div>
</template>
<style scoped>
.t-transcripts { margin-top: 8px; }
.sample-columns { display: grid; grid-template-columns: repeat(var(--sample-count), minmax(0, 1fr)); gap: 4px; }
</style>
