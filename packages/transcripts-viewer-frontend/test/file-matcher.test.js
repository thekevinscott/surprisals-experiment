import test from 'node:test'
import assert from 'node:assert/strict'
import {matchFile} from '../src/composables/fileMatcher.js'
test('specific solutions renderer takes precedence over general JSON',()=>{
  assert.equal(matchFile('problem/solutions.json'),'solutions')
  assert.equal(matchFile('problem/input_output.json'),'json')
  assert.equal(matchFile('windows/0/metadata.JSON'),'json')
  assert.equal(matchFile('u/transcript.jsonl'),'transcript')
  assert.equal(matchFile('usage.jsonl'),'jsonl')
  assert.equal(matchFile('problem/question.txt'),'text')
  assert.equal(matchFile('main.py'),'python')
  assert.equal(matchFile('src/MAIN.PY'),'python')
})
