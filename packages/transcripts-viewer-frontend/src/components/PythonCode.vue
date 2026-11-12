<script setup>
import {computed} from 'vue'
import {highlightPython} from '../composables/pythonCode.js'
import 'highlight.js/styles/github.css'
const props=defineProps({text:String})
const highlighted=computed(()=>highlightPython(props.text))
</script>
<template><pre class="python-code"><code class="hljs language-python" v-html="highlighted"></code></pre></template>
<style scoped>
.python-code { margin:0;tab-size:4;white-space:pre;overflow:auto;font-size:12px; }
.python-code code { display:block;padding:8px; }
</style>
