import {readdir,stat} from 'node:fs/promises'
import {readFileSync} from 'node:fs'
import {directories} from './topology.js'
import {join} from 'node:path'
import {quote} from './experiment-database.js'

const summarySql=readFileSync(new URL('./summary.sql',import.meta.url),'utf8')
const chartsSql=readFileSync(new URL('./charts.sql',import.meta.url),'utf8')
const indexSql=readFileSync(new URL('./index.sql',import.meta.url),'utf8')
const diagramSql=readFileSync(new URL('./diagram.sql',import.meta.url),'utf8')
const sampleSql=readFileSync(new URL('./sample.sql',import.meta.url),'utf8')
// const incomplete='Incomplete usage records were skipped; costs may be partial.'

async function readable(db,table,run=null) {
  const [row]=await db.query(`SELECT error FROM ${table} WHERE error IS NOT NULL AND (:run IS NULL OR run=:run) ORDER BY path LIMIT 1`,{run})
  if(row)throw Error(row.error)
}

async function summaries(db,runs,run=null) {
  await readable(db,'documents',run)
  const topology=[]
  for(const id of runs)for(const entry of await directories(join(db.root,'runs',id)))topology.push({...entry,run:id})
  const [{payload}]=await db.query(summarySql,{run,now:Date.now(),directories:JSON.stringify(topology)})
  const rows=JSON.parse(payload)
  const [charts]=await db.query(chartsSql,{rows:payload})
  JSON.parse(charts.payload).forEach((chart,index)=>{rows[index].charts=chart})
  return rows
}

export async function runSummary(db,run,warnings) {
  const [row]=await summaries(db,[run],run)
  if(!row)throw Object.assign(Error(`Cannot read ${join(db.root,'runs',run,'run.json')}: ENOENT`),{code:'ENOENT'})
  // if(warnings&&(await db.query('SELECT 1 FROM transcript_lines WHERE run=? AND incomplete LIMIT 1',[run])).length)warnings.add(incomplete)
  return row
}

export async function readRunIndex(db) {
  await readable(db,'identities')
  const [{payload}]=await db.query(indexSql)
  return JSON.parse(payload)
}

export async function readExperiment(db) {
  let entries
  try { entries = await readdir(join(db.root,'runs'), {withFileTypes:true}) }
  catch (error) {
    if (error.code !== 'ENOENT') throw error
    await stat(db.root) // Only a missing runs/ is empty; a missing experiment is an error.
    return {rows:[],warnings:[]}
  }
  const index=await readRunIndex(db)
  const rows=await summaries(db,index.rows.map(row=>row.id))
  const [{payload}]=await db.query(`WITH missing AS (SELECT count(*)-json_array_length(:rows) AS n FROM json_each(:folders) WHERE value)
  SELECT json_object('rows',json(:rows),
  'warnings',json((SELECT json_group_array(value) FROM (
   -- SELECT :incomplete AS value WHERE EXISTS(SELECT 1 FROM transcript_lines WHERE incomplete) UNION ALL
   SELECT n||' run folders have no run.json yet and are omitted from the run list.' AS value FROM missing WHERE n>0))),
  'strategyOptions',json(:options)) AS payload`,{rows:JSON.stringify(rows),folders:JSON.stringify(entries.map(entry=>entry.isDirectory())),options:JSON.stringify(index.strategyOptions)})
  return JSON.parse(payload)
}

export async function runSettings(db,run) {
  const [row]=await db.query(`SELECT body FROM documents WHERE run=? AND kind='settings.json'`,[run])
  return row?JSON.parse(row.body):{}
}

export async function readRunDiagram(db,run) {
  await readable(db,'documents',run)
  const settings=await runSettings(db,run)
  const [{payload}]=await db.query(diagramSql,{run,directories:JSON.stringify(await directories(join(db.root,'runs',run))),forkTurns:settings.fork_turns??null,strategy:settings.cap_strategy??null,samples:settings.t_samples??null})
  return JSON.parse(payload)
}

export async function readSample(db,run,{window,fork,turn,sample}) {
  await readable(db,'documents',run)
  const position={window:Number(window),fork:Number(fork),turn:Number(turn),sample:Number(sample)}
  const topology=await directories(join(db.root,'runs',run))
  const prefix=`runs/${run}/`,base=`${prefix}windows/${window}/forks/${fork}/turns/${turn}/ts/${sample}/attempts/`
  const attempts=topology.filter(entry=>entry.kind==='attempt'&&['window','fork','turn','sample'].every(key=>entry[key]===position[key])).map(entry=>entry.attempt)
  const files=attempts.length?await db.query(attempts.flatMap(attempt=>[
    `SELECT ${attempt} AS attempt,'src' AS kind,path,size FROM ${quote(`./${base}${attempt}/src/**/*`)}`,
    `SELECT ${attempt} AS attempt,'transcript' AS kind,path,size FROM ${quote(`./${base}${attempt}/transcripts/*/*.jsonl`)}`,
  ]).join(' UNION ALL ')):[]
  for(const file of files)file.path=file.path.slice(prefix.length)
  const [{payload}]=await db.query(sampleSql,{run,...position,directories:JSON.stringify(topology),files:JSON.stringify(files)})
  return {attempts:JSON.parse(payload)}
}
