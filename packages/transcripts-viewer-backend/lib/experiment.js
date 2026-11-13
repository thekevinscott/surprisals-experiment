import { readdir, stat } from 'node:fs/promises'
import { basename, join, relative, resolve } from 'node:path'
import {instanceLaunch} from './aws-launch.js'
import {withDatabase} from './experiment-database.js'

// Batched SQL queries gather structured artifacts without reading transcript bodies.
async function artifacts(directory, db) {
  const patterns = ['{run,settings}.json', 'windows/*/forks/*/turns/*/metadata.json',
    'advices/*/advice.txt', 'advices/*/advice.json',
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
  const passing = [], scored = []
  const forks = new Map()
  let latest = (await stat(join(directory, 'run.json'))).mtimeMs
  for (const {id} of turnsInDatabase) {
    const path=`${id}/metadata.json`
    const turnDirectory = join(directory, path, '..')
    const [, window, , fork, , turn] = path.split('/')
    windows.add(window)
    const key = `${window}/${fork}`
    if (!forks.has(key)) forks.set(key, {window:Number(window),id:Number(fork),turns:0,passing:[],scored:[]})
    const branch = forks.get(key)
    const depth = Number(window) === 0 ? Number(turn) : Number(window) * stride + Number(turn)
    if (Number.isFinite(depth)) branch.turns = Math.max(branch.turns, depth + 1)
    const metadata = await json(join(directory, path))
    latest = Math.max(latest, (await stat(join(directory, path))).mtimeMs)
    turns = Math.max(turns, Number(window) === 0 ? Number(turn) + 1 : Number.isFinite(stride) ? Number(window) * stride + Number(turn) + 1 : 0)
    for (const artifact of store.rows.filter(row=>row.path.startsWith(id+'/ts/'))) latest = Math.max(latest,(await stat(join(directory,artifact.path))).mtimeMs)
    const samples = await readSamples(turnDirectory, directory, store)
    const passed = !!(settings.t_samples && samples.length === settings.t_samples && samples.every(s => s.latest?.tests?.all_passed && !s.latest.generation?.timed_out && !s.latest.generation?.error))
    if (/^advices\/[a-f0-9]+$/.test(metadata.advice ?? '')) {
      const advice = await json(join(directory, metadata.advice, 'advice.json'), true)
      if (Number.isFinite(advice?.score)) {
        if (Number.isFinite(depth)) {
          scored.push([depth, advice.score, passed])
          branch.scored.push([depth, advice.score, passed])
        }
        if (passed) {
          if (best === null || advice.score < best) { best = advice.score; bestTarget = `windows/${window}/forks/${fork}/turns/${turn}` }
          if (Number.isFinite(depth)) {
            passing.push([depth, advice.score])
            branch.passing.push([depth, advice.score])
          }
        }
      }
    }
  }
  const uCost = includeCosts ? await costs(directory, 'windows/*/forks/*/u/transcript.jsonl', r => r.usage ?? (r.role === 'assistant' ? {} : null), warnings, database) : null
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
    windowPositions: [...windows].map(Number).sort((a,b)=>a-b).map(id=>({id,depth:id===0 ? 0 : id*stride})).filter(window=>Number.isFinite(window.depth)),
    samples: settings.t_samples ?? null,
    forkTurns: settings.fork_turns, soloTurns: settings.window_solo_turns,
    scored: scored.sort((a,b) => a[0] - b[0]),
    passing: passing.sort((a, b) => a[0] - b[0] || a[1] - b[1]),
    forks: [...forks.values()].sort((a,b) => a.window - b.window || a.id - b.id).map(fork => ({
      ...fork, scored: fork.scored.sort((a,b) => a[0] - b[0]), passing: fork.passing.sort((a,b) => a[0] - b[0]),
    })),
    awsLaunched: await instanceLaunch(directory,database),
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
  if(!database)return withDatabase(directory,null,db=>readRunIndex(directory,db),{relations:false})
  const json=(...args)=>database.json(...args)
  const root = resolve(directory), rows = []
  for (const {path} of await database.files('runs/*/run.json')) {
    const run = join(root,path,'..')
    rows.push(runIdentity(run, await json(join(run,'run.json')), await json(join(run,'settings.json'),true) ?? {}))
  }
  return {rows:rows.sort((a,b)=>a.id.localeCompare(b.id))}
}

export async function readExperiment(directory, getDatabase) {
  directory = resolve(directory)
  const runsDirectory = join(directory, 'runs')
  let entries
  try { entries = await readdir(runsDirectory, {withFileTypes:true}) }
  catch (error) {
    if (error.code !== 'ENOENT') throw error
    await stat(directory) // Only a missing runs/ is empty; a missing experiment is an error.
    return {rows:[],warnings:[]}
  }
  const warnings = new Set()
  const rows = []
  const index=await readRunIndex(directory)
  for (const {id} of index.rows) {
    const root=join(runsDirectory,id)
    rows.push(await runSummary(root,warnings,getDatabase?.(root)))
  }
  const folders = entries.filter(entry => entry.isDirectory()).length
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
  return `windows/${window}/forks/${fork}/u/transcript.jsonl`
}

async function readFork(directory, id, forkTurns, source, unit, sourceRoot, store) {
  const optionalText=store.text
  const turns = []
  for (const id of await numericDirectories(join(directory,'turns'))) {
    const metadataText = await optionalText(join(directory, 'turns', String(id), 'metadata.json'))
    const metadata = metadataText ? JSON.parse(metadataText) : null
    let advice = null
    let adviceSource = null
    let measurement = null
    let tokens = null
    let adviceMetadata = null
    if (typeof metadata?.advice === 'string') {
      adviceSource = `${metadata.advice}/advice.txt`
      advice = await optionalText(join(sourceRoot, adviceSource))
      adviceMetadata = await store.json(join(sourceRoot, metadata.advice, 'advice.json'),true)
      measurement = adviceMetadata?.score ?? null
      tokens = adviceMetadata?.tokens ?? null
    }
    const samples = await readSamples(join(directory, 'turns', String(id)), sourceRoot, store)
    turns.push({ id, error: metadata?.error ?? null, source: relative(sourceRoot, join(directory, 'turns', String(id))), transcriptPath: source, samples, advice, adviceSource, measurement, unit, tokens, metadata, adviceMetadata })
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
      const source = transcriptPath(id,fork)
      forks.push(await readFork(join(directory,`windows/${id}/forks/${fork}`), fork, settings.fork_turns, source, unit, directory, store))
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
