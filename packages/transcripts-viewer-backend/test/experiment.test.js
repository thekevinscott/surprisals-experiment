import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { readExperiment } from '../lib/experiment.js'

async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), 'transcripts-viewer-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  const put = async (path, data) => {
    const file = join(root, 'runs/run-one', path)
    await mkdir(dirname(file), { recursive: true })
    await writeFile(file, typeof data === 'string' ? data : JSON.stringify(data))
  }
  await put('run.json', {
    params: { 'problem-dir': '../data/APPS/test/0054', 'cap-strategy': 'characters' },
    invocations: [{ started: '2026-11-01T01:00:00Z', ended: '2026-11-01T03:30:00Z', exit_code: 0 }],
  })
  await put('settings.json', { t_samples: 2, fork_turns: 10, window_solo_turns: 30 })
  return { root, put }
}

test('best score requires all samples, retries use latest test, forks share depth; costs include all U contexts', async t => {
  const { root, put } = await fixture(t)
  for (const [fork, score] of [[0, 12], [1, 3]]) {
    const turn = `windows/1/forks/${fork}/turns/2`
    await put(`${turn}/metadata.json`, { advice: `advices/a${fork}` })
    await put(`advices/a${fork}/advice.json`, { score })
    await put(`${turn}/ts/0/attempts/0/tests.json`, { all_passed: true })
    await put(`${turn}/ts/1/attempts/0/tests.json`, { all_passed: fork === 0 })
  }
  await put('windows/1/forks/0/turns/2/ts/0/attempts/1/tests.json', { all_passed: true })
  await put('windows/0/forks/0/u/transcript.jsonl', '{"role":"system","content":"instructions"}\n{"role":"user","content":"question"}\n{"role":"assistant","content":"reply","completion_id":"one","usage":{"cost":1}}\n')
  await put('windows/1/forks/0/u/transcript.jsonl', '{"role":"assistant","content":"reply","completion_id":"one","usage":{"cost":1}}\n{"role":"assistant","content":"partial","_complete":false,"completion_id":"two","usage":{"cost":2}}\n')
  await put('windows/1/forks/0/turns/2/ts/0/attempts/0/transcripts/session/one.jsonl', '{"type":"message","message":{"usage":{"cost":{"total":4}}}}\n')
  const { rows } = await readExperiment(root)
  assert.equal(rows.length, 1)
  assert.equal(rows[0].problem, '0054')
  assert.equal(rows[0].best, 12)
  assert.deepEqual(rows[0].passing, [[42, 12]])
  assert.deepEqual(rows[0].forks, [
    {window:1,id:0,turns:43,passing:[[42,12]],scored:[[42,12,true]]},
    {window:1,id:1,turns:43,passing:[],scored:[[42,3,false]]},
  ])
  assert.equal(rows[0].turns, 43)
  assert.equal(rows[0].windows, 1)
  assert.equal(rows[0].elapsed, 9000)
  assert.equal(rows[0].uCost, 3)
  assert.equal(rows[0].tCost, 4)
  assert.equal(rows[0].modelCost, 7)
  assert.equal(rows[0].status, 'Complete')
})

test('missing prices stay unknown, incomplete usage is flagged, unfinished folders are reported', async t => {
  const { root, put } = await fixture(t)
  await put('run.json', { created: '2026-11-01T00:00:00Z', invocations: [{ started: '2026-11-01T00:00:00Z' }] })
  await put('windows/0/forks/0/u/transcript.jsonl', '{"usage":{"cost":0}}\n{"usage":{}}\n{"truncated":')
  await mkdir(join(root, 'runs/arriving'))
  const data = await readExperiment(root)
  assert.equal(data.rows[0].uCost, null)
  assert.equal(data.rows[0].tCost, null)
  assert.equal(data.rows[0].modelCost, null)
  assert.equal(data.rows[0].status, 'Open')
  assert.equal(data.warnings.length, 2)
})

test('rejects a missing experiment and malformed metadata with its file path', async t => {
  const { root, put } = await fixture(t)
  await assert.rejects(readExperiment(join(root, 'absent')), /ENOENT/)
  await put('run.json', '{broken')
  await assert.rejects(readExperiment(root), /Cannot read .*run.json/)
})

test('single U transcript keeps cost unknown when an assistant reply has null usage', async t => {
  const {root,put}=await fixture(t)
  const records=[
    {role:'system',content:'Instructions'},
    {role:'user',content:'Question'},
    {role:'assistant',content:'Advice',reasoning:'Reasoning remains in the source',timestamp:'2026-11-12T12:00:00Z',completion_id:'priced',usage:{cost:1},_complete:true},
    {role:'assistant',content:'Partial',reasoning:'Partial reasoning',timestamp:'2026-11-12T12:01:00Z',completion_id:'unpriced',usage:null,_complete:false},
  ]
  await put('windows/0/forks/0/u/transcript.jsonl',records.map(JSON.stringify).join('\n')+'\n')
  assert.equal((await readExperiment(root)).rows[0].uCost,null)
})

 test('scored series includes failed T turns and spans no-advice gaps and windows', async t => {
  const {root,put}=await fixture(t)
  for(const [window,turn,score,passed] of [[0,38,8,true],[0,39,30,false],[1,1,6,true]]){
    const dir=`windows/${window}/forks/0/turns/${turn}`,advice=`advices/a${window}${turn}`
    await put(`${dir}/metadata.json`,{advice})
    await put(`${advice}/advice.json`,{score})
    for(const sample of [0,1])await put(`${dir}/ts/${sample}/attempts/0/tests.json`,{all_passed:passed})
  }
  await put('windows/1/forks/0/turns/0/metadata.json',{advice:null,error:'U failed'})
  const {rows:[row]}=await readExperiment(root)
  assert.deepEqual(row.scored,[[38,8,true],[39,30,false],[41,6,true]])
  assert.deepEqual(row.passing,[[38,8],[41,6]])
  assert.equal(row.best,6)
  assert.deepEqual(row.forks.map(f=>f.scored),[[[38,8,true],[39,30,false]],[[41,6,true]]])
})
