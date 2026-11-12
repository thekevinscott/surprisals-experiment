<script setup>
import { computed } from 'vue'
import ContentPanel from './ContentPanel.vue'
import TokenText from './TokenText.vue'
const props = defineProps({ label: String, reasoning: String, metadata: Object, verbatim: Boolean, source: String, sourceLine: Number, text: String, tokens: Array, measurement: String, stateKey: String })
const length = computed(() => Array.from(props.text ?? '').length)
</script>
<template>
  <ContentPanel class="text-section" :title="label" :metadata="metadata" :source="source" :source-line="sourceLine" :state-key="stateKey" :summary="measurement" :expanded="verbatim" :preview="!verbatim" :collapsible="verbatim || length > 200" v-slot="{ expanded, toggle }">
    <details v-if="reasoning" class="record-reasoning"><summary>Reasoning</summary><pre>{{ reasoning }}</pre></details>
    <p v-if="text == null" class="unavailable">File not recorded</p>
    <p v-else-if="verbatim || expanded || length <= 200"><TokenText :text="text" :tokens="tokens" /></p>
    <p v-else><TokenText :text="text" :tokens="tokens" :end="100" /><button class="ellipsis-toggle" :aria-label="`Expand ${label}`" @click="toggle">...</button><TokenText :text="text" :tokens="tokens" :start="length - 100" /></p>
    <div v-if="tokens?.length" class="token-legend">Token surprisal <span></span> 0–20+ bits</div>
  </ContentPanel>
</template>
<style scoped>
.record-reasoning { margin: 4px 0; font-size: 12px; }
.record-reasoning summary { cursor: pointer; color: #657186; }
.record-reasoning pre { margin: 4px 0; white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; }
.text-section { margin-top: 4px; }
p { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 11px; line-height: 1.5; }
.unavailable { color: #657186; }
.ellipsis-toggle { color: #214da3; font: inherit; font-weight: 700; border: 0; padding: 0 3px; background: #e5edf9; cursor: pointer; }
.token-legend { font-size: 9px; color: #657186; display: flex; align-items: center; gap: 5px; margin-top: 4px; }
.token-legend span { width: 40px; height: 8px; background: linear-gradient(to right, #fffce6, #e0a000); border-radius: 2px; }
</style>
