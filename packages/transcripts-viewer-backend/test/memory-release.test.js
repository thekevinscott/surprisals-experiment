import test from 'node:test'
import assert from 'node:assert/strict'
import {spawnSync} from 'node:child_process'
import {EventEmitter} from 'node:events'
import {createEvents} from '../lib/events.js'
import {ExperimentDatabase} from '../lib/experiment-database.js'

function collected(script){
  const result=spawnSync(process.execPath,['--expose-gc','--input-type=module','-e',`
    import assert from 'node:assert/strict'
    import {mkdtemp,writeFile,rm} from 'node:fs/promises'
    import {tmpdir} from 'node:os'
    import {join} from 'node:path'
    const root=await mkdtemp(join(tmpdir(),'viewer-retention-'))
    try { ${script} } finally { await rm(root,{recursive:true,force:true}) }
  `],{encoding:'utf8'})
  assert.equal(result.status,0,result.stderr)
}
test('finished transcript reads do not retain any per-file contents',()=>{
  collected(`
    const {createTranscriptReader}=await import(${JSON.stringify(new URL('../lib/transcript-blocks.js',import.meta.url).href)})
    const {ExperimentDatabase}=await import(${JSON.stringify(new URL('../lib/experiment-database.js',import.meta.url).href)})
    const {mkdir}=await import('node:fs/promises')
    const path=i=>'runs/r/windows/0/forks/'+i+'/u/transcript.jsonl'
    for(let i=0;i<20;i++){
      await mkdir(join(root,path(i),'..'),{recursive:true})
      await writeFile(join(root,path(i)),JSON.stringify({role:'user',content:String(i)+'x'.repeat(100000)}))
    }
    const db=new ExperimentDatabase(root),read=createTranscriptReader(db),references=[]
    for(let i=0;i<20;i++)references.push(new WeakRef(await read.blocks(path(i),0,1)))
    await new Promise(setImmediate);global.gc()
    assert(references.every(ref=>ref.deref()===undefined),'reader retains completed file payloads')
    assert.equal((await read.metadata(path(0))).total,1)
    await db.close()
  `)
})
test('database serialization tail does not hold the last query result',async()=>{
  const db=Object.create(ExperimentDatabase.prototype)
  db.pending=Promise.resolve();db.db={query:async()=>[{content:'large payload'}]}
  assert.deepEqual(await db.query('SELECT content'),[{content:'large payload'}])
  assert.equal(await db.pending,undefined)
})
test('last unsubscribe discards its snapshot immediately, including during a replacement read',async t=>{
  const events=createEvents({interval:60000});t.after(()=>events.close())
  const reply=()=>{const raw=new EventEmitter();raw.writeHead=()=>{};raw.write=text=>raw.frames.push(text);raw.end=()=>raw.emit('close');raw.frames=[];return {raw,hijack(){}}}
  const first=reply();events.multiplex(first,['/api/runs/a'],async()=>({content:'old'}))
  await new Promise(setImmediate)
  assert(first.raw.frames.some(frame=>frame.includes('old')))
  first.raw.emit('close')
  let complete
  const second=reply();events.multiplex(second,['/api/runs/a'],()=>new Promise(resolve=>{complete=resolve}))
  assert(!second.raw.frames.some(frame=>frame.includes('old')),'unsubscribed data must not seed a new subscription')
  complete({content:'new'});await new Promise(setImmediate)
  assert(second.raw.frames.some(frame=>frame.includes('new')))
  second.raw.emit('close')
})
