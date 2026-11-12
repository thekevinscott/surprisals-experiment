import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { readRunDiagram, readTurnTranscript, readSample } from '../lib/experiment.js'

test('actual fork IDs, solo continuation, root transcript ownership and reply matching', async t => {
  const root = await mkdtemp(join(tmpdir(), 'run-diagram-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  const put = async (path, value) => {
    await mkdir(dirname(join(root, path)), { recursive: true })
    await writeFile(join(root, path), value)
  }
  const reply = (content, reasoning) => JSON.stringify({ role: 'assistant', content, reasoning, _complete: true })
  await put('u/transcripts/messages.jsonl', [JSON.stringify({ role: 'system', content: 'System rules' }), JSON.stringify({ role: 'user', content: 'Question', _reset: true }), reply('root', 'root thinking')].join('\n'))
  await put('windows/0/forks/0/turns/0/u/advice.txt', 'root')
  await put('windows/0/forks/0/turns/0/metadata.json', JSON.stringify({ advice: 'advices/ab' }))
  await put('advices/ab/advice.json', JSON.stringify({ score: 17.5, tokens: [['root', 17.5]] }))
  await put('windows/0/forks/2/turns/0/u/advice.txt', 'first')
  await put('windows/0/forks/2/turns/2/u/advice.txt', 'solo')
  await put('windows/0/forks/2/u/transcripts/messages.jsonl', [
    reply('first', 'thinking'),
    JSON.stringify({ role: 'assistant', content: 'first', reasoning: 'replayed context' }),
    JSON.stringify({ role: 'assistant', content: 'partial', _complete: false }),
    reply('solo', 'last thinking'),
  ].join('\n'))
  await put('windows/1/forks/5/turns/0/u/advice.txt', 'no transcript')
  await put('windows/0/forks/0/turns/0/ts/2/attempts/0/transcripts/session/old.jsonl', JSON.stringify({ type: 'message', message: { role: 'assistant', content: 'old attempt' } }))
  const message = { type: 'message', id: 'message-one', message: { role: 'assistant', content: [{ type: 'thinking', thinking: 'Reasoning' }, { type: 'text', text: 'Solution' }] } }
  await put('windows/0/forks/0/turns/0/ts/2/attempts/1/transcripts/session/new.jsonl', [JSON.stringify(message), JSON.stringify(message)].join('\n'))
  await put('windows/0/forks/0/turns/0/ts/2/attempts/1/src/main.py', 'print(42)')
  await put('windows/0/forks/0/turns/0/ts/2/attempts/1/tests.json', JSON.stringify({ passed: 1, total: 1, all_passed: true }))
  const windows = await readRunDiagram(root, { fork_turns: 2, cap_strategy: 'surprisal' })
  assert.deepEqual(windows.map(w => w.forks.map(f => f.id)), [[0, 2], [5]])
  assert.deepEqual(windows.map(w => w.continuedForks), [[2], []])
  const firstFork = windows[0].forks[0]
  const messages = await readTurnTranscript(root,0,0,0)
  assert.deepEqual(messages.map(message => message.role), ['system', 'user', 'assistant'])
  assert.equal(messages[0].raw, JSON.stringify({ role: 'system', content: 'System rules' }))
  assert.equal(windows[0].forks[0].parallel[0].advice, 'root')
  assert.equal(windows[0].forks[0].parallel[0].measurement, 17.5)
  assert.equal(windows[0].forks[0].parallel[0].unit, 'bits')
  assert.deepEqual(windows[0].forks[0].parallel[0].tokens, [['root', 17.5]])
  const sample = await readSample(join(root, firstFork.parallel[0].samples[0].source),root)
  assert.equal(sample.attempts.length, 2)
  assert.equal('messages' in sample.attempts[0], false)
  assert.equal(sample.attempts[1].transcriptFiles.length, 1)
  assert.equal(sample.attempts[1].files[0].name, 'main.py')
  assert.equal('transcript' in firstFork.parallel[0], false)
  assert.equal('transcriptSource' in firstFork, false)
  assert.equal('messageIds' in firstFork.parallel[0], false)
  assert.equal((await readTurnTranscript(root,0,2,2)).at(-1).raw, reply('solo', 'last thinking'))
  assert.equal('messages' in firstFork, false)
  assert.equal('context' in firstFork.parallel[0], false)
  assert.equal('attempts' in firstFork.parallel[0].samples[0], false)
  assert.deepEqual(await readTurnTranscript(root,1,5,0), [])
})
