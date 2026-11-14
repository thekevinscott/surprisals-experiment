import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join,dirname} from 'node:path'
import {createApi} from '../server.js'

test('experiment costs cover every run, refresh usage, and skip graph artifacts',async t=>{
  const root=await mkdtemp(join(tmpdir(),'experiment-costs-')),app=createApi(root)
  t.after(async()=>{await app.close();await rm(root,{recursive:true,force:true})})
  const put=async(path,value)=>{const full=join(root,path);await mkdir(dirname(full),{recursive:true});await writeFile(full,typeof value==='string'?value:JSON.stringify(value))}
  const get=async()=>{const r=await app.inject('/api/runs/costs');assert.equal(r.statusCode,200,r.body);return r.json()}
  assert.deepEqual(await get(),{rows:[],warnings:[]})
  for(const id of ['one','two']) {
    await put(`runs/${id}/run.json`,{created:'2026-11-13T00:00:00Z',invocations:[{ended:'2026-11-13T01:00:00Z'}]})
    await put(`runs/${id}/stderr-0.txt`,'2026-11-13T00:00:00Z instance launched\n')
    await put(`runs/${id}/windows/0/forks/0/u/transcript.jsonl`,JSON.stringify({role:'assistant',completion_id:'same-id-across-runs',usage:{cost:1}})+'\n')
    await put(`runs/${id}/windows/0/forks/0/turns/0/ts/0/attempts/0/transcripts/session/t.jsonl`,JSON.stringify({type:'message',message:{usage:{cost:{total:2}}}})+'\n')
    // These must not be parsed by this cost-only endpoint.
    await put(`runs/${id}/windows/0/forks/0/turns/0/metadata.json`,'invalid graph metadata')
  }
  const data=await get()
  assert.deepEqual(data.rows.map(r=>[r.id,r.uCost,r.tCost]),[['one',1,2],['two',1,2]])
  assert.equal(data.rows[0].awsLaunched,'2026-11-13T00:00:00.000Z')
  assert.equal(data.rows[0].ended,'2026-11-13T01:00:00Z')
  await put('runs/one/windows/0/forks/0/u/transcript.jsonl',JSON.stringify({role:'assistant',usage:{cost:4}})+'\n')
  assert.equal((await get()).rows[0].uCost,4)
})
