<script setup>
import TSample from './TSample.vue'
defineProps({ samples: Array, columns: Number })
</script>
<template>
  <div v-if="samples.length" class="t-transcripts">
    <div class="sample-columns" :style="{ '--sample-count': columns }">
      <TSample v-for="sample in samples" :key="sample.id" :sample="sample" />
    </div>
  </div>
</template>
<style scoped>
.sample-columns { display: grid; grid-template-columns: repeat(var(--sample-count), minmax(56px, 1fr)); gap: 4px; }
</style>
