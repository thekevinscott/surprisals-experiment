import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join,dirname} from 'node:path'
import {CostDatabase} from '../lib/cost-database.js'
import {eventually} from './support/eventually.js'

async function fixture(t){
 const root=await mkdtemp(join(tmpdir(),'viewer-sql-cost-')),db=new CostDatabase(root,{experiment:true})
 t.after(async()=>{await db.close();await rm(root,{recursive:true,force:true})})
 const put=async(path,data)=>{const target=join(root,path);await mkdir(dirname(target),{recursive:true});await writeFile(target,typeof data==='string'?data:JSON.stringify(data))}
 return {db,put}
}
test('SQL costs deduplicate per run and kind, retain anonymous records and report missing prices',async t=>{
 const {db,put}=await fixture(t)
 for(const id of ['one','two']){
  await put(`runs/${id}/run.json`,{created:'2026-11-13T00:00:00Z'})
  await put(`runs/${id}/windows/0/forks/0/u/transcript.jsonl`,[
   {role:'assistant',completion_id:'shared',usage:{cost:1}},
   {role:'assistant',completion_id:'shared',usage:{cost:99}},
   {role:'assistant',usage:{cost:2}}, {role:'assistant',usage:{cost:3}},
  ].map(JSON.stringify).join('\n'))
  await put(`runs/${id}/windows/0/forks/0/turns/0/ts/0/attempts/0/transcripts/session/t.jsonl`,JSON.stringify({type:'message',completion_id:'shared',message:{usage:{cost:{total:4}}}}))
 }
 await eventually(async()=>assert.deepEqual((await db.snapshot()).rows.map(row=>[row.uCost,row.tCost]),[[6,4],[6,4]]))
 let data=await db.snapshot()
 assert.deepEqual(data.rows.map(row=>[row.uCost,row.tCost]),[[6,4],[6,4]])
 assert.equal(data.breakdown.total,20)
 await put('runs/one/windows/0/forks/0/u/transcript.jsonl','{"role":"assistant","usage":null}\n{"partial":')
 await eventually(async()=>assert.equal((await db.snapshot()).rows[0].uCost,null))
 data=await db.snapshot()
 assert.equal(data.rows[0].uCost,null)
 assert.equal(data.breakdown.missing.u,1)
 assert.equal(data.warnings.length,1)
 await put('runs/one/windows/0/forks/0/u/transcript.jsonl','{"usage":{"cost":1}}\n')
 await eventually(async()=>assert.equal((await db.snapshot()).rows[0].uCost,1))
 await put('runs/one/windows/0/forks/0/u/transcript.jsonl','{"usage":{"cost":2}}\n')
 await eventually(async()=>assert.equal((await db.snapshot()).rows[0].uCost,2,'same-size live rewrite'))
})
test('SQL estimates use launch times, freeze ended runs, include shared pods once and share a clock',async t=>{
 const {db,put}=await fixture(t)
 for(const id of ['one','two']){
  await put(`runs/${id}/run.json`,{created:'2026-11-13T00:00:00Z',...(id==='one'?{ended:'2026-11-13T01:00:00Z'}:{})})
  await put(`runs/${id}/stderr-0.txt`,'invalid instance launched\n2026-11-13T00:00:00Z instance launched\n')
 }
 await put('runpod-costs/pod.json',{id:'pod',gpu:'H100',costPerHr:2,start:'2026-11-13T00:00:00Z'})
 const now=Date.parse('2026-11-13T02:00:00Z')
 await eventually(async()=>assert.equal((await db.snapshot(now)).breakdown.total,4.3024))
 const data=await db.snapshot(now)
 assert.equal(data.asOf,now)
 assert.equal(data.rows[0].awsCost,0.1008)
 assert.equal(data.rows[1].awsCost,0.2016)
 assert.equal(data.breakdown.aws,0.3024)
 assert.equal(data.breakdown.runpod,4)
 assert.equal(data.breakdown.total,4.3024)
 assert.equal((await db.snapshot(now+3600000)).breakdown.runpod,6)
 assert.equal((await db.snapshot(0)).breakdown.runpod,0)
})
