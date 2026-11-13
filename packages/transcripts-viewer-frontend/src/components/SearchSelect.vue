<script setup>
import { useId,ref,inject,onMounted,watch } from 'vue'
import {useUrlState} from '../composables/urlState.js'
import Select from 'primevue/select'
const props=defineProps({ label: String, modelValue: String, options: Array, searchable:{type:Boolean,default:true} })
const emit = defineEmits(['update:modelValue'])
const id = useId(),select=ref(null),scope=inject('viewStateKey',()=> '')
const opened=useUrlState(()=>`select:${scope()}:${props.label}:open`,false)
const filter=useUrlState(()=>`select:${scope()}:${props.label}:filter`,'')
onMounted(()=>{if(opened.value)select.value.show();select.value.filterValue=filter.value})
watch(filter,value=>{if(select.value)select.value.filterValue=value})
</script>
<template>
  <div class="search-select">
    <label :for="id">{{ label }}</label>
    <Select ref="select" @show="opened=true" @hide="opened=false;filter=''" @filter="filter=$event.value" :input-id="id" :aria-label="label" :model-value="modelValue" :options="options"
      option-label="value" option-value="value" :filter-fields="['value', 'description']" :filter="searchable" reset-filter-on-hide
      :filter-placeholder="`Search ${label}`" :filter-input-props="{ 'aria-label': `Search ${label}` }"
      size="small" @update:model-value="emit('update:modelValue', $event)">
      <template #option="{ option }">
        <div class="select-option"><span>{{ option.value }}</span><small>{{ option.description }}</small></div>
      </template>
    </Select>
  </div>
</template>
