import test from 'node:test'
import assert from 'node:assert/strict'
import {fileSize} from '../src/composables/fileSize.js'
test('unknown file sizes never render NaN',()=>{assert.equal(fileSize(undefined),'');assert.equal(fileSize(2048),'2 KB')})

test('small files show bytes rather than zero kilobytes', () => {
  assert.equal(fileSize(417), '417 B')
  assert.equal(fileSize(1536), '1.5 KB')
})
