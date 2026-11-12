<script setup>
import { computed, inject, onMounted, onBeforeUnmount, provide, ref, watch } from 'vue'
import Panel from 'primevue/panel'
import Button from 'primevue/button'
import SourceActions from './SourceActions.vue'
const props = defineProps({ title: String, href: String, local: Boolean, metadata: Object, source: String, sourceLine: Number, summary: String, stateKey: String, preview: Boolean, expandLabel: String, collapseLabel: String, collapsible: { type: Boolean, default: true } })
const model = defineModel('expanded', { default: false })
const shared = inject('disclosureState', null)
const local = props.local || inject('localDisclosure', false)
provide('localDisclosure', local)
const parentPath = inject('disclosurePath', () => '')
const path = computed(() => `${parentPath()}/${props.stateKey ?? props.title}`)
provide('disclosurePath', () => path.value)
const expanded = computed({
  get: () => (local ? undefined : shared?.expanded.get(path.value)) ?? model.value,
  set: value => { if (shared && !local) shared.expanded.set(path.value, value); model.value = value },
})
watch(expanded, value => { model.value = value })
const content = ref(null)
const inner = ref(null)
const visible = computed(() => expanded.value || props.preview || !props.collapsible)
const toggle = () => { expanded.value = !expanded.value }
let observer, frame
onMounted(() => {
  if (!shared) return
  observer = new ResizeObserver(() => {
    cancelAnimationFrame(frame)
    frame = requestAnimationFrame(() => shared.measure(path.value, inner.value, inner.value.getBoundingClientRect().height))
  })
  observer.observe(inner.value)
})
onBeforeUnmount(() => { observer?.disconnect(); cancelAnimationFrame(frame); shared?.remove(path.value, inner.value) })
defineExpose({ toggle, setExpanded: value => { expanded.value = value } })
</script>
<template>
  <Panel :header="title" class="content-panel" :toggleable="collapsible && !preview" :collapsed="!visible" @update:collapsed="expanded = !$event">
    <template #header><div class="panel-label"><strong>{{ title }}</strong><a v-if="href" class="permalink" :href="href" :aria-label="`Link to ${title}`" :title="`Link to ${title}`">#</a><span v-if="summary">{{ summary }}</span></div></template>
    <template #icons>
      <SourceActions :title="title" :metadata="metadata" :source="source" :source-line="sourceLine" />
      <Button v-if="preview && collapsible" text size="small" :label="expanded ? (collapseLabel || 'Show less') : (expandLabel || 'Show all')" :aria-expanded="expanded" :aria-label="`${expanded ? 'Collapse' : 'Expand'} ${title}`" @click="toggle" />
    </template>
    <div ref="content" class="disclosure-body" :style="{ minHeight: visible && shared?.heights.get(path) ? `${shared.heights.get(path)}px` : undefined }">
      <div ref="inner" v-show="visible" class="box-content"><slot :expanded="expanded" :toggle="toggle" /></div>
    </div>
  </Panel>
</template>
<style scoped>
.content-panel { margin:0; min-width:0; --p-panel-header-padding:4px; --p-panel-content-padding:0 4px 4px; --p-panel-border-radius:6px; }
.panel-label { display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 8px; min-width:0; }
.permalink { color:#697b94;text-decoration:none;font-size:12px; }
.panel-label strong { font-size:12px; }
.panel-label span { font-size:10px; color:#657186; }
.content-panel :deep(.p-panel-header-actions) { display:flex; align-items:center; }
.content-panel :deep(.p-panel-toggle-button) { width:24px; height:24px; }
.content-panel :deep(.p-button) { font-size:10px; padding:3px 5px; }
.disclosure-body { display:grid; grid-template-columns:minmax(0,1fr); align-content:start; }
.box-content { min-width:0; }
</style>
