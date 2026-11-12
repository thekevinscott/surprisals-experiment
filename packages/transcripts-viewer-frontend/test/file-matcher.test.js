import test from 'node:test'
import assert from 'node:assert/strict'
import {matchFile,fileRoute} from '../src/composables/fileMatcher.js'
test('specific solutions renderer takes precedence over general JSON',()=>{
  assert.equal(matchFile('problem/solutions.json'),'solutions')
  assert.equal(matchFile('problem/input_output.json'),'json')
  assert.equal(matchFile('windows/0/metadata.JSON'),'json')
  assert.equal(matchFile('u/messages.jsonl'),'transcript')
  assert.equal(matchFile('usage.jsonl'),'jsonl')
  assert.equal(matchFile('problem/question.txt'),'text')
})
test('file routes retain encoded paths and JSONL physical line links',()=>{
  const name='windows/a b/#test.jsonl',src='/api/runs/r/files/'+name
  const route=fileRoute(`#files/${encodeURIComponent(name)}?${new URLSearchParams({src,line:'49'})}`)
  assert.equal(route.get('name'),name);assert.equal(route.get('src'),src);assert.equal(route.get('line'),'49')
  assert.equal(fileRoute('#jsonl?src=x&name=a.jsonl&line=3').get('line'),'3')
  assert.equal(fileRoute('#run/example'),null)
})
