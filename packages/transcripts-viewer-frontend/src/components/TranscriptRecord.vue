<script setup>
import { computed, ref } from 'vue'
import { recordPresentation } from '../composables/recordPresentation.js'
import TextSection from './TextSection.vue'
import ContentPanel from './ContentPanel.vue'
const props = defineProps({ label: String, message: Object, stateKey: String })
const text = ref(null)
const presentation = computed(() => recordPresentation(props.message.raw ?? text.value ?? ''))
const error = ref('')
const loading = ref(false)
async function load() {
  loading.value = true
  try {
    const response = await fetch(props.message.url)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    text.value = await response.text()
  } catch (e) { error.value = e.message }
  finally { loading.value = false }
}
</script>
<template>
  <TextSection v-if="message.raw !== null || text !== null" verbatim :label="label" :state-key="stateKey" :source="message.source" :source-line="message.line" :text="presentation.text" :reasoning="presentation.reasoning" :metadata="presentation.metadata" />
  <ContentPanel v-else :title="label" :source="message.source" :source-line="message.line" :state-key="stateKey" preview :collapsible="false">
    <button @click="load" :disabled="loading">{{ loading ? 'Loading…' : 'Load original record' }}</button>
    <p v-if="error">{{ error }}</p>
  </ContentPanel>
</template>
