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
  await put('u/transcripts/usage.jsonl', '{"completion_id":"one","usage":{"cost":1}}\n')
  await put('windows/1/forks/0/u/transcripts/usage.jsonl', '{"completion_id":"one","usage":{"cost":1}}\n{"completion_id":"two","usage":{"cost":2}}\n')
  await put('windows/1/forks/0/turns/2/ts/0/attempts/0/transcripts/session/one.jsonl', '{"type":"message","message":{"usage":{"cost":{"total":4}}}}\n')
  const { rows } = await readExperiment(root)
  assert.equal(rows.length, 1)
  assert.equal(rows[0].problem, '0054')
  assert.equal(rows[0].best, 12)
  assert.deepEqual(rows[0].passing, [[42, 12]])
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
  await put('u/transcripts/usage.jsonl', '{"usage":{"cost":0}}\n{"usage":{}}\n{"truncated":')
  await mkdir(join(root, 'runs/arriving'))
  const data = await readExperiment(root)
  assert.equal(data.rows[0].uCost, null)
  assert.equal(data.rows[0].tCost, null)
  assert.equal(data.rows[0].modelCost, null)
  assert.equal(data.rows[0].status, 'Open')
  assert.equal(data.warnings.length, 2)
})

test('rejects a directory without runs and malformed metadata with its file path', async t => {
  const { root, put } = await fixture(t)
  await assert.rejects(readExperiment(join(root, 'absent')), /ENOENT/)
  await put('run.json', '{broken')
  await assert.rejects(readExperiment(root), /Cannot read .*run.json/)
})
