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
    const read=createTranscriptReader(),references=[]
    for(let i=0;i<20;i++){
      const path=join(root,String(i))
      await writeFile(path,JSON.stringify({role:'user',content:String(i)+'x'.repeat(100000)}))
      references.push(new WeakRef(await read(path)))
    }
    await new Promise(setImmediate);global.gc()
    assert(references.every(ref=>ref.deref()===undefined),'reader retains completed file payloads')
    assert.equal((await read(join(root,'0'))).metadata.total,1)
  `)
})
test('finished usage scans do not retain per-file records',()=>{
  collected(`
    const {ExperimentDatabase}=await import(${JSON.stringify(new URL('../lib/experiment-database.js',import.meta.url).href)})
    const db=new ExperimentDatabase(root,{relations:false}),references=[]
    try{
      for(let i=0;i<20;i++){
        await writeFile(join(root,String(i)),JSON.stringify({completion_id:String(i),usage:{cost:i}}))
        references.push(new WeakRef(await db.usage(String(i),record=>record.usage)))
      }
      await new Promise(setImmediate);global.gc()
      assert(references.every(ref=>ref.deref()===undefined),'usage scan retains completed record arrays')
      assert.equal((await db.usage('0',record=>record.usage)).records[0].cost,0)
    }finally{await db.close()}
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
