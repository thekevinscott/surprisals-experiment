<script setup>
import {useColorMode} from '@vueuse/core'
import Select from 'primevue/select'
const mode=useColorMode({storageKey:'viewer-color-scheme',emitAuto:true,modes:{light:'',dark:'app-dark'}})
const options=[{label:'System',value:'auto'},{label:'Light',value:'light'},{label:'Dark',value:'dark'}]
</script>
<template><Select v-model="mode" :options="options" option-label="label" option-value="value" size="small" aria-label="Color theme" /></template>
