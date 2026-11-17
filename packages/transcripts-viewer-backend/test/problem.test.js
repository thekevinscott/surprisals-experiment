import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { readProblem } from '../lib/problem.js'
import { ExperimentDatabase } from '../lib/experiment-database.js'

test('copied runs resolve exact data-relative problem path and expose missing files', async () => {
  const root = await mkdtemp(join(tmpdir(), 'viewer-problem-'))
  await mkdir(join(root, 'experiments/example'), { recursive: true })
  const db = new ExperimentDatabase(join(root, 'experiments/example'))
  try {
    const dir = join(root, 'data/APPS/test/42')
    await mkdir(dir, { recursive: true })
    await writeFile(join(dir, 'question.txt'), 'Question 42')
    await writeFile(join(dir, 'solutions.json'), '["print(42)"]')
    const files = await readProblem(db, join(root, 'experiments/example'), '/remote/repo/data/APPS/test/42')
    assert.deepEqual(files.map(f => f.text), ['Question 42', null, '["print(42)"]'])
    assert.deepEqual(await readProblem(db, root, undefined), [])
  } finally { await db.close(); await rm(root, { recursive: true, force: true }) }
})
