import test from 'node:test'
import assert from 'node:assert/strict'
import { ref } from 'vue'
import { useColumnLayout } from '../src/composables/useColumnLayout.js'

test('fork resizing covers only columns to the right, snaps to bounds, and restores', () => {
  const layout = useColumnLayout(ref([0, 1, 2, 3].map(id => ({ id }))))
  layout.resize(0, 3)
  assert.deepEqual(layout.hidden.value.map(f => f.id), [1, 2])
  assert.equal(layout.isVisible(3), true)
  assert.equal(layout.columnSpan(0), 3)
  layout.resize(2, 4)
  assert.equal(layout.columnSpan(2), 2)
  assert.deepEqual(layout.hidden.value.map(f => f.id), [3])
  layout.reset()
  assert.deepEqual(layout.hidden.value, [])
})
