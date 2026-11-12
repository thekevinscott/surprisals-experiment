import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises'
import {join,dirname} from 'node:path'
import {tmpdir} from 'node:os'
import {ExperimentDatabase} from '../lib/experiment-database.js'

test('turn index and raw artifacts track retries and live writes',async t=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-db-'))
  const put=async(path,value)=>{await mkdir(dirname(join(root,path)),{recursive:true});await writeFile(join(root,path),JSON.stringify(value))}
  const db=new ExperimentDatabase(root)
  t.after(async()=>{await db.close();await rm(root,{recursive:true})})
  assert.deepEqual(await db.query('SELECT * FROM turns'),[])
  const turn='windows/0/forks/0/turns/0',sample=turn+'/ts/0'
  await put(turn+'/metadata.json',{advice:null})
  assert.equal((await db.query('SELECT id FROM turns'))[0].id,turn)
  for(const id of [0,1]){
    await put(`${sample}/attempts/${id}/generation.json`,{exit_code:0})
    await put(`${sample}/attempts/${id}/tests.json`,{cases:[{index:0,passed:!!id,status:id?'passed':'failed'}]})
  }
  assert.equal((await db.files(`${sample}/attempts/*/generation.json`)).length,2)
  assert.deepEqual(await db.json(join(root,sample,'attempts/1/tests.json')),{cases:[{index:0,passed:true,status:'passed'}]})
  await rm(join(root,sample,'attempts/1/generation.json'))
  assert.equal((await db.files(`${sample}/attempts/*/generation.json`)).length,1,'earlier retry artifact remains')
  await rm(join(root,turn,'metadata.json'))
  assert.deepEqual(await db.query('SELECT * FROM turns'),[])
})

test('usage costs refresh after same-size rewrites without reparsing unchanged transcripts',async t=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-usage-')),db=new ExperimentDatabase(root,{relations:false})
  t.after(async()=>{await db.close();await rm(root,{recursive:true})})
  const path=join(root,'usage.jsonl'),select=record=>record.usage
  await writeFile(path,'{"usage":{"cost":1}}\n')
  assert.equal((await db.usage('usage.jsonl',select)).records[0].cost,1)
  await writeFile(path,'{"usage":{"cost":2}}\n')
  assert.equal((await db.usage('usage.jsonl',select)).records[0].cost,2)
})
