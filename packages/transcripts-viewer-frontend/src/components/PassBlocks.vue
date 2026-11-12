<script setup>
import {passBlocks} from '../composables/outcomes.js'
defineProps({passed: Number, total: Number, unit: {type: String, default: 'tests'}})
</script>
<template>
  <span class="pass-blocks" role="img" :aria-label="`${passed}/${total} ${unit} passed`" :title="`${passed}/${total} ${unit} passed`">
    <span v-for="(outcome, index) in passBlocks(passed, total)" :key="index" class="pass-block" :class="outcome" aria-hidden="true"></span>
  </span>
</template>
<style scoped>
.pass-blocks { display: inline-flex; flex-wrap: wrap; gap: 3px; vertical-align: middle; }
.pass-block { width: 8px; height: 8px; border-radius: 2px; }
.passed { background: #15803d; }
.failed { background: #b91c1c; }
</style>
