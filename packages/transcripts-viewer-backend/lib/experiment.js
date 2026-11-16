import { readdir, stat } from 'node:fs/promises'
import {readFileSync} from 'node:fs'
import {CostDatabase} from './cost-database.js'
import {directories} from './topology.js'
import { basename, join, relative, resolve } from 'node:path'
import {runRuntime} from './runtime.js'
import {instanceLaunch} from './aws-launch.js'
import {withDatabase} from './experiment-database.js'

const summarySql=readFileSync(new URL('./summary.sql',import.meta.url),'utf8')
const chartsSql=readFileSync(new URL('./charts.sql',import.meta.url),'utf8')

export async function experimentCosts(directory,database) {
  const db=database?.(directory)
  if(db?.costs)return db.costs.snapshot()
  const costs=new CostDatabase(directory,{experiment:true})
  try{return await costs.snapshot()}finally{await costs.close()}
}

export async function runSummary(directory,warnings=new Set(),database,{includeCosts=true,costRow}={}) {
  if(!database)return withDatabase(directory,null,db=>runSummary(directory,warnings,db,{includeCosts,costRow}))
  const index=await readRunIndex(directory,database)
  const identity=index.rows.find(row=>row.id===basename(directory))
  if(!identity)throw Object.assign(Error(`Cannot read ${join(directory,'run.json')}: ENOENT`),{code:'ENOENT'})
  const [{payload}]=await database.query(summarySql,{id:identity.id,problem:identity.problem,strategy:identity.strategy,now:Date.now(),directories:JSON.stringify(await directories(directory))})
  const row=JSON.parse(payload)
  const [{meta}]=await database.query('SELECT meta FROM run_info')
  const runtime=await runRuntime(directory,JSON.parse(meta),database)
  Object.assign(row,runtime,{duration:runtime.elapsed})
  if(includeCosts&&!costRow){
    const costs=new CostDatabase(directory)
    try{const snapshot=await costs.snapshot();costRow=snapshot.rows[0];for(const warning of snapshot.warnings)warnings.add(warning)}finally{await costs.close()}
  }
  Object.assign(row,costRow??{uCost:null,tCost:null,modelCost:null,awsLaunched:await instanceLaunch(directory,database)})
  const [charts]=await database.query(chartsSql,{row:JSON.stringify(row)})
  row.charts=JSON.parse(charts.payload)
  return row
}

const indexSql=readFileSync(new URL('./index.sql',import.meta.url),'utf8')
export async function readRunIndex(directory,database) {
  if(!database)return withDatabase(directory,null,db=>readRunIndex(directory,db),{relations:false})
  const [{payload}]=await database.query(indexSql)
  return JSON.parse(payload)
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
  const costs=await experimentCosts(directory,getDatabase)
  for(const warning of costs.warnings)warnings.add(warning)
  for (const {id} of index.rows) {
    const root=join(runsDirectory,id)
    rows.push(await runSummary(root,warnings,getDatabase?.(root),{costRow:costs.rows.find(row=>row.id===id)}))
  }
  const finish=async db=>{
    const [{payload}]=await db.query(`WITH rows AS (SELECT value FROM json_each(:rows)),
    missing AS (SELECT count(*)-(SELECT count(*) FROM rows) AS n FROM json_each(:folders) WHERE value->>'directory')
    SELECT json_object('rows',json((SELECT json_group_array(json(value)) FROM (SELECT value FROM rows ORDER BY value->>'strategy',value->>'problem',value->>'id'))),
    'warnings',json((SELECT json_group_array(value) FROM (SELECT value FROM json_each(:warnings) UNION ALL SELECT n||' run folders have no run.json yet and are omitted from the run list.' FROM missing WHERE n>0))),
    'strategyOptions',json(:options)) AS payload`,{rows:JSON.stringify(rows),folders:JSON.stringify(entries.map(entry=>({directory:entry.isDirectory()}))),warnings:JSON.stringify([...warnings]),options:JSON.stringify(index.strategyOptions)})
    return JSON.parse(payload)
  }
  return getDatabase?finish(getDatabase(directory)):withDatabase(directory,null,finish,{relations:false})
}

const diagramSql=readFileSync(new URL('./diagram.sql',import.meta.url),'utf8')
const sampleSql=readFileSync(new URL('./sample.sql',import.meta.url),'utf8')

export async function readRunDiagram(directory,settings,database) {
  if(!database)return withDatabase(directory,null,db=>readRunDiagram(directory,settings,db))
  const [{payload}]=await database.query(diagramSql,{directories:JSON.stringify(await directories(directory)),forkTurns:settings.fork_turns??null,strategy:settings.cap_strategy??null,samples:settings.t_samples??null})
  return JSON.parse(payload)
}

export async function readSample(directory,sourceRoot,database) {
  if(!database)return withDatabase(sourceRoot,null,db=>readSample(directory,sourceRoot,db))
  const sample=relative(sourceRoot,directory)
  const files=await database.files(`${sample}/attempts/*/{src/**/*,transcripts/*/*.jsonl}`)
  const [{payload}]=await database.query(sampleSql,{sample,directories:JSON.stringify(await directories(sourceRoot)),files:JSON.stringify(files)})
  return {attempts:JSON.parse(payload)}
}

export async function readAttempt(directory,id,sourceRoot,database) {
  const sample=await readSample(join(directory,'../..'),sourceRoot,database)
  return sample.attempts.find(attempt=>attempt.id===id)
}
