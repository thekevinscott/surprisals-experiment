<script setup>
import ContentPanel from './ContentPanel.vue'
import PassBlocks from './PassBlocks.vue'
import JsonContent from './JsonContent.vue'
defineProps({ missingReason: { type: String, default: 'Tests not recorded' }, results: Object, source: String })
</script>
<template>
  <ContentPanel title="Test results" :source="results ? source : undefined" class="test-results">
    <template #summary>
      <PassBlocks v-if="results?.passed != null && results?.total != null" :passed="results.passed" :total="results.total" :cases="results.cases" :source="source" />
      <span v-else>{{ results ? `${results.passed ?? '?'} / ${results.total ?? '?'} passed` : missingReason }}</span>
    </template>
    <p v-if="!results">{{ missingReason }}</p>
    <template v-else>
      <p v-if="results.duration_seconds != null">Duration: {{ results.duration_seconds }}s</p>
      <ContentPanel v-for="test in results.cases" :key="test.index" :title="`Case ${test.index}`" :source="source" :summary="test.status ?? (test.passed ? 'Passed' : 'Failed')" class="test-case">
        <JsonContent :text="JSON.stringify(test)" />
      </ContentPanel>
    </template>
  </ContentPanel>
</template>
<style scoped>
.test-results, .test-case { margin-top: 8px; }
p { font-size: 11px; margin: 0 0 8px; }
.test-case :deep(p) { font-family: ui-monospace, monospace; }
</style>
