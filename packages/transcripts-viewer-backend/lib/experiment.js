import { readdir, stat } from 'node:fs/promises'
import { basename, join, relative, resolve } from 'node:path'
import { uContext } from './u-context.js'
import {withDatabase} from './experiment-database.js'

// Batched SQL queries gather the structured artifacts for each request. Transcript
// bodies stay outside this snapshot and are read only by their own endpoint.
async function artifacts(directory, db) {
  const patterns = ['{run,settings}.json', 'windows/*/forks/*/turns/*/metadata.json',
    'windows/*/forks/*/turns/*/u/advice.txt', 'advices/*/advice.json',
    'windows/*/forks/*/turns/*/ts/*/attempts/*/{tests,generation}.json']
  const rows=[]
  for(const pattern of patterns)rows.push(...await db.files(pattern,{content:true}))
  const byPath=new Map(rows.map(row=>[resolve(directory,row.path),row]))
  for(const row of rows.filter(row=>row.path.endsWith('.json'))) {
    try {row.parsed=JSON.parse(row.content)}catch(error){throw Error(`Cannot read ${join(directory,row.path)}: ${error.message}`)}
  }
  return {
    rows,
    text: async (path) => byPath.get(resolve(path))?.content ?? null,
    json: async (path, optional=false) => {
      const row=byPath.get(resolve(path))
      if(!row){if(optional)return null;throw Error(`Cannot read ${path}: ENOENT`)}
      return row.parsed
    },
  }
}

async function costs(directory, pattern, select, warnings, db) {
  let total = 0
  let count = 0
  let missing = false
  const seen = new Set()
  for (const {path} of await db.files(pattern)) {
    const usage=await db.usage(path,select)
    if(usage.incomplete)warnings.add('Incomplete usage records were skipped; costs may be partial.')
    for(const {id:key,cost} of usage.records){
      // Replayed completions across transcript files count only once.
      if(key&&seen.has(key))continue
      if(key)seen.add(key)
      count++
      if (typeof cost === 'number') total += cost
      else missing = true
    }
  }
  return count && !missing ? total : null
}

export async function runSummary(directory, warnings = new Set(), database, {includeCosts=true}={}) {
  if(!database)return withDatabase(directory,null,db=>runSummary(directory,warnings,db,{includeCosts}))
  const store=await artifacts(directory,database), json=store.json
  const turnsInDatabase=await database.query('SELECT id FROM turns ORDER BY id')
  const meta = await json(join(directory, 'run.json'))
  const settings = await json(join(directory, 'settings.json'), true) ?? {}
  const current = meta.invocations?.at(-1) ?? meta
  const stride = settings.fork_turns + settings.window_solo_turns
  let turns = 0
  const windows = new Set()
  let best = null
  let bestTarget = null
  const passing = []
  let latest = (await stat(join(directory, 'run.json'))).mtimeMs
  for (const {id} of turnsInDatabase) {
    const path=`${id}/metadata.json`
    const turnDirectory = join(directory, path, '..')
    const [, window, , fork, , turn] = path.split('/')
    windows.add(window)
    const metadata = await json(join(directory, path))
    latest = Math.max(latest, (await stat(join(directory, path))).mtimeMs)
    turns = Math.max(turns, Number(window) === 0 ? Number(turn) + 1 : Number.isFinite(stride) ? Number(window) * stride + Number(turn) + 1 : 0)
    for (const artifact of store.rows.filter(row=>row.path.startsWith(id+'/ts/'))) latest = Math.max(latest,(await stat(join(directory,artifact.path))).mtimeMs)
    const samples = await readSamples(turnDirectory, directory, store)
    if (settings.t_samples && samples.length === settings.t_samples && samples.every(s => s.latest?.tests?.all_passed && !s.latest.generation?.timed_out && !s.latest.generation?.error)
        && /^advices\/[a-f0-9]+$/.test(metadata.advice ?? '')) {
      const advice = await json(join(directory, metadata.advice, 'advice.json'), true)
      if (typeof advice?.score === 'number') {
        if (best === null || advice.score < best) { best = advice.score; bestTarget = `windows/${window}/forks/${fork}/turns/${turn}` }
        const depth = Number(window) === 0 ? Number(turn) : Number(window) * stride + Number(turn)
        if (Number.isFinite(depth)) passing.push([depth, advice.score])
      }
    }
  }
  const uCost = includeCosts ? await costs(directory, '{u/transcript.jsonl,windows/*/forks/*/u/transcript.jsonl}', r => r.usage ?? (r.role === 'assistant' ? {} : null), warnings, database) : null
  const tCost = includeCosts ? await costs(directory, 'windows/*/forks/*/turns/*/ts/*/attempts/*/transcripts/*/*.jsonl', r => r.type === 'message' ? r.message?.usage : null, warnings, database) : null
  const started = current.started ?? meta.created
  const ended = current.ended
  const end = ended ? Date.parse(ended) : latest
  const elapsed = started && Number.isFinite(end) ? Math.max(0, (end - Date.parse(started)) / 1000) : null
  return {
    ...runIdentity(directory, meta, settings),
    exit: current.exit_code ?? null,
    status: ended ? (current.exit_code === 0 ? 'Complete' : 'Stopped / failed') : 'Open',
    cause: current.error ?? (current.exit_code === 0 ? null : current.ended_by) ?? null,
    started, ended, observed: new Date(latest).toISOString(), elapsed, turns, best, bestTarget,
    windows: windows.size,
    samples: settings.t_samples ?? null,
    passing: passing.sort((a, b) => a[0] - b[0] || a[1] - b[1]),
    uCost, tCost,
    modelCost: uCost !== null && tCost !== null ? uCost + tCost : null,
  }
}

function runIdentity(directory, meta, settings) {
  return {
    id: basename(directory),
    problem: basename(meta.params?.['problem-dir'] ?? settings.problem_dir ?? 'Unknown'),
    strategy: meta.params?.['cap-strategy'] ?? settings.cap_strategy ?? 'Unknown',
  }
}

// The selector index must not scan every turn or transcript before a run opens.
export async function readRunIndex(directory, database) {
  if(!database)return withDatabase(join(directory,'runs'),null,db=>readRunIndex(directory,db),{relations:false})
  const json=(...args)=>database.json(...args)
  const root = join(resolve(directory), 'runs'), rows = []
  for (const {path} of await database.files('*/run.json')) {
    const run = join(root,path,'..')
    rows.push(runIdentity(run, await json(join(run,'run.json')), await json(join(run,'settings.json'),true) ?? {}))
  }
  return {rows:rows.sort((a,b)=>a.id.localeCompare(b.id))}
}

export async function readExperiment(directory, getDatabase) {
  directory = resolve(directory)
  const runsDirectory = join(directory, 'runs')
  if (!(await stat(runsDirectory)).isDirectory()) throw new Error(`Expected a runs directory in ${directory}`)
  const warnings = new Set()
  const rows = []
  const index=await readRunIndex(directory)
  for (const {id} of index.rows) {
    const root=join(runsDirectory,id)
    rows.push(await runSummary(root,warnings,getDatabase?.(root)))
  }
  const folders = (await readdir(runsDirectory, { withFileTypes: true })).filter(entry => entry.isDirectory()).length
  if (folders > rows.length) warnings.add(`${folders - rows.length} run folders have no run.json yet and are omitted from the run list.`)
  rows.sort((a, b) => a.strategy.localeCompare(b.strategy) || a.problem.localeCompare(b.problem) || a.id.localeCompare(b.id))
  return { rows, warnings: [...warnings] }
}

async function numericDirectories(directory) {
  try {
    return (await readdir(directory, {withFileTypes:true})).filter(e => e.isDirectory() && /^\d+$/.test(e.name)).map(e => Number(e.name)).sort((a,b)=>a-b)
  } catch (error) { if (error.code === 'ENOENT') return []; throw error }
}

function transcriptPath(window, fork) {
  return Number(window) === 0 && Number(fork) === 0 ? 'u/transcript.jsonl' : `windows/${window}/forks/${fork}/u/transcript.jsonl`
}

export async function readTurnTranscript(root, window, fork, turn, database) {
  if(!database)return withDatabase(root,null,db=>readTurnTranscript(root,window,fork,turn,db),{relations:false})
  const optionalText=path=>database.text(path,true)
  const source = transcriptPath(window, fork)
  const {replies,messages} = parseUTranscript(await optionalText(join(root,source)) ?? '', source)
  const directory = join(root, `windows/${window}/forks/${fork}/turns`)
  let cursor = 0
  for (const id of await numericDirectories(directory)) {
    const advice = await optionalText(join(directory, String(id), 'u/advice.txt'))
    const index = advice === null ? -1 : replies.findIndex((r,i) => i >= cursor && r.content === advice)
    const reply = index < 0 ? null : replies[index]
    if (reply) cursor = index + 1
    if (id === Number(turn)) return uContext(messages, reply?.context)
  }
  return []
}

async function readFork(directory, id, forkTurns, source, unit, sourceRoot, store) {
  const optionalText=store.text
  const turns = []
  for (const id of await numericDirectories(join(directory,'turns'))) {
    const advice = await optionalText(join(directory, 'turns', String(id), 'u/advice.txt'))
    const metadataText = await optionalText(join(directory, 'turns', String(id), 'metadata.json'))
    const metadata = metadataText ? JSON.parse(metadataText) : null
    let measurement = null
    let tokens = null
    if (/^advices\/[a-f0-9]+$/.test(metadata?.advice ?? '')) {
      const adviceMetadata = await optionalText(join(directory, '../../../../', metadata.advice, 'advice.json'))
      if (adviceMetadata) {
        const scored = JSON.parse(adviceMetadata)
        measurement = scored.score ?? null
        tokens = unit === 'bits' ? scored.tokens ?? null : null
      }
    }
    const samples = await readSamples(join(directory, 'turns', String(id)), sourceRoot, store)
    turns.push({ id, error: metadata?.error ?? null, source: relative(sourceRoot, join(directory, 'turns', String(id))), transcriptPath: source, samples, advice, measurement, unit, tokens })
  }
  return {
    id, source: relative(sourceRoot, directory), transcriptPath: source,
    parallel: forkTurns == null ? turns : turns.filter(t => t.id < forkTurns),
    solo: forkTurns == null ? [] : turns.filter(t => t.id >= forkTurns),
  }
}

export async function readRunDiagram(directory, settings, database) {
  if(!database)return withDatabase(directory,null,db=>readRunDiagram(directory,settings,db))
  const store=await artifacts(directory,database)
  const unit = settings.cap_strategy === 'surprisal' ? 'bits' : settings.cap_strategy === 'characters' ? 'chars' : 'score'
  const windows = []
  for (const id of await numericDirectories(join(directory,'windows'))) {
    const forks = []
    for (const fork of await numericDirectories(join(directory,`windows/${id}/forks`))) {
      forks.push(await readFork(join(directory,`windows/${id}/forks/${fork}`), fork, settings.fork_turns, transcriptPath(id,fork), unit, directory, store))
    }
    forks.sort((a, b) => a.id - b.id)
    windows.push({ id, forks, continuedForks: forks.filter(f => f.solo.length).map(f => f.id) })
  }
  return windows.sort((a, b) => a.id - b.id)
}

async function readOutcome(directory, id, store) {
  const json=store.json
  return {id, tests:await json(join(directory,'tests.json'),true), generation:await json(join(directory,'generation.json'),true)}
}

async function readSamples(directory, sourceRoot, store) {
  const samples = []
  for (const id of await numericDirectories(join(directory,'ts'))) {
    const sampleDir = join(directory,'ts',String(id))
    const attempts = await numericDirectories(join(sampleDir,'attempts'))
    const latest = attempts.length ? await readOutcome(join(sampleDir,'attempts',String(attempts.at(-1))),attempts.at(-1),store) : null
    // The overview needs status only. Full cases/stdout belong to the sample endpoint.
    const summary=latest && {id:latest.id,
      tests:latest.tests && {all_passed:latest.tests.all_passed,passed:latest.tests.passed,total:latest.tests.total},
      generation:latest.generation && {timed_out:latest.generation.timed_out,error:latest.generation.error,exit_code:latest.generation.exit_code}}
    samples.push({id,source:relative(sourceRoot,sampleDir),latest:summary})
  }
  return samples
}

export async function readSample(directory, sourceRoot, database) {
  if(!database)return withDatabase(sourceRoot,null,db=>readSample(directory,sourceRoot,db),{relations:false})
  const attempts = []
  for (const id of await numericDirectories(join(directory,'attempts'))) attempts.push(await readAttempt(join(directory,'attempts',String(id)),id,sourceRoot,database))
  return {attempts}
}

export async function readAttempt(directory, id, sourceRoot, database) {
  if(!database)return withDatabase(sourceRoot,null,db=>readAttempt(directory,id,sourceRoot,db),{relations:false})
  const prefix=relative(sourceRoot,directory)
  const transcriptFiles=(await database.files(`${prefix}/transcripts/*/*.jsonl`)).map(row=>({name:row.path,source:row.path,text:null,bytes:row.size}))
  const files=(await database.files(`${prefix}/src/**/*`)).map(row=>({name:relative(join(prefix,'src'),row.path),source:row.path,bytes:row.size,text:null}))
  const store={json:(...args)=>database.json(...args)}
  return {...await readOutcome(directory,id,store),source:prefix,testsSource:`${prefix}/tests.json`,transcriptFiles,files}
}

// Parse only for navigation labels and turn matching; display the original line.
export function transcriptRecord(raw) {
  let record
  try { record = JSON.parse(raw) } catch { return { role: 'Unparsed record', raw, record: null } }
  return { role: record.message?.role ?? record.role ?? record.type ?? 'Record', raw, record }
}

export function parseUTranscript(text, source) {
  const replies = [], messages = []
  let system = null, start = 0
  for (const [lineIndex, line] of text.split('\n').entries()) {
    if (!line) continue
    const { record: entry, ...message } = transcriptRecord(line)
    const index = messages.length
    messages.push({ ...message, source, line: lineIndex + 1, inContext: !!entry && entry._complete !== false })
    if (!entry || entry._complete === false) continue
    if (entry._reset) start = index
    if (entry.role === 'system') system = index
    if (entry.role === 'assistant' && entry._complete === true) replies.push({ ...entry, context: { system, start, end: index } })
  }
  return { messages, replies }
}
