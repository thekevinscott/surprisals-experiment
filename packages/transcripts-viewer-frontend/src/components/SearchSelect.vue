<script setup>
import { useId } from 'vue'
import Select from 'primevue/select'
defineProps({ label: String, modelValue: String, options: Array })
const emit = defineEmits(['update:modelValue'])
const id = useId()
</script>
<template>
  <div class="search-select">
    <label :for="id">{{ label }}</label>
    <Select :input-id="id" :aria-label="label" :model-value="modelValue" :options="options"
      option-label="value" option-value="value" :filter-fields="['value', 'description']" filter reset-filter-on-hide
      :filter-placeholder="`Search ${label}`" :filter-input-props="{ 'aria-label': `Search ${label}` }"
      size="small" @update:model-value="emit('update:modelValue', $event)">
      <template #option="{ option }">
        <div class="select-option"><span>{{ option.value }}</span><small>{{ option.description }}</small></div>
      </template>
    </Select>
  </div>
</template>
