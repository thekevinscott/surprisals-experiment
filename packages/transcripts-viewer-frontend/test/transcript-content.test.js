import test from 'node:test'
import assert from 'node:assert/strict'
import {transcriptContent} from '../src/composables/transcriptFile.js'

test('popup content excludes metadata and preserves content whitespace and incomplete records', () => {
  assert.equal(transcriptContent('{"role":"assistant","content":"hello\\n\\nworld","reasoning":"private reasoning","_complete":false}'), 'hello\n\nworld')
  assert.equal(transcriptContent('{"message":{"role":"user","content":"  text  "}}'), '  text  ')
  assert.equal(transcriptContent('{"role":"assistant","_complete":false}'), '')
  assert.equal(transcriptContent(''), '')
  assert.equal(transcriptContent('broken'), '')
  assert.equal(transcriptContent('{"content":[{"type":"text","text":"hello"}]}'), '[\n  {\n    "type": "text",\n    "text": "hello"\n  }\n]')
})
