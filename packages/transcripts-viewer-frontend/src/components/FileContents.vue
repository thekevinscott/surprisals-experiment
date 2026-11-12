<script setup>
import { inject } from 'vue'
import { fileSize } from '../composables/fileSize.js'
import { openFile } from '../composables/filePreview.js'
import SourceActions from './SourceActions.vue'
defineProps({ file: Object, iconOnly: Boolean })
const sourceUrl=inject('sourceUrl')
</script>
<template>
  <div class="file-content" :class="{'icon-only':iconOnly}">
    <button v-if="!iconOnly" class="file-name" type="button" @click="openFile(sourceUrl(file.source))">{{ file.name }} <small>{{ fileSize(file.bytes) }}</small></button>
    <SourceActions :title="file.name" :source="file.source" />
  </div>
</template>
<style scoped>
.file-content { display: flex; align-items: center; gap: 2px; min-width: 0; }
.file-name { min-width: 0; padding: 2px 0; border: 0; background: none; color: #254c7f; text-align: left; overflow-wrap: anywhere; font: inherit; font-size: 11px; cursor: pointer; }
small { color: #657186; font-size: 9px; }
</style>
