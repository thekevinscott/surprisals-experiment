<script setup>
import { ref,inject } from 'vue'
import {fetchJson,useLazyResource} from '../composables/api.js'
import { attemptState } from '../composables/outcomes.js'
import ContentPanel from './ContentPanel.vue'
import TAttempt from './TAttempt.vue'
const props=defineProps({ sample: Object })
const expanded = ref(false)
const apiUrl=inject('apiUrl')
const {data,loading,error}=useLazyResource(expanded,signal=>fetchJson(apiUrl(props.sample.source),signal))
</script>
<template>
  <ContentPanel local v-model:expanded="expanded" class="t-sample" :data-sample="sample.id" :title="`T${sample.id}`" :summary="attemptState(sample.latest)">
    <div v-if="expanded" class="sample-scroll">
      <p v-if="loading">Loading attempts…</p><p v-else-if="error" role="alert">{{ error }}</p>
      <TAttempt v-for="attempt in (loading ? [] : data?.attempts ?? [])" :key="attempt.id" :attempt="attempt" />
    </div>
  </ContentPanel>
</template>
<style scoped>
.t-sample { min-width: 0; margin: 0; background: #f8fafc; border: 1px solid #d0dae7; border-radius: 6px; }
.sample-scroll { height: 260px; overflow-y: auto; padding: 0 8px 8px; scrollbar-gutter: stable; }
p { font-size: 11px; color: #657186; }
</style>
