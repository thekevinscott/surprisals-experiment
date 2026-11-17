import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises'
import {join,dirname} from 'node:path'
import {tmpdir} from 'node:os'
import {ExperimentDatabase} from '../lib/experiment-database.js'
import {eventually} from './support/eventually.js'

test('turn index and raw artifacts track retries and live writes',async t=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-db-'))
  const put=async(path,value)=>{await mkdir(dirname(join(root,path)),{recursive:true});await writeFile(join(root,path),JSON.stringify(value))}
  const db=new ExperimentDatabase(root)
  t.after(async()=>{await db.close();await rm(root,{recursive:true})})
  await eventually(async()=>assert.deepEqual(await db.query("SELECT turn FROM documents WHERE run='r' AND kind='metadata.json'"),[]))
  const turn='runs/r/windows/0/forks/0/turns/0',sample=turn+'/ts/0'
  await put(turn+'/metadata.json',{advice:null})
  await eventually(async()=>assert.equal((await db.query("SELECT turn FROM documents WHERE run='r' AND kind='metadata.json'"))[0]?.turn,0))
  for(const id of [0,1]){
    await put(`${sample}/attempts/${id}/generation.json`,{exit_code:0})
    await put(`${sample}/attempts/${id}/tests.json`,{cases:[{index:0,passed:!!id,status:id?'passed':'failed'}]})
  }
  assert.equal((await db.files(`${sample}/attempts/*/generation.json`)).length,2)
  await eventually(async()=>assert.deepEqual(JSON.parse((await db.query("SELECT body FROM documents WHERE run='r' AND kind='tests.json' AND attempt=1"))[0].body),{cases:[{index:0,passed:true,status:'passed'}]}))
  await rm(join(root,sample,'attempts/1/generation.json'))
  assert.equal((await db.files(`${sample}/attempts/*/generation.json`)).length,1,'earlier retry artifact remains')
  await rm(join(root,turn,'metadata.json'))
  await eventually(async()=>assert.deepEqual(await db.query("SELECT turn FROM documents WHERE run='r' AND kind='metadata.json'"),[]))
})
