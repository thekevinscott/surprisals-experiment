import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,readFile,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {database} from './support/database.js'

test('charts parse input once and aggregate score bounds once per run',async t=>{
 const root=await mkdtemp(join(tmpdir(),'viewer-chart-bounds-'))
 t.after(()=>rm(root,{recursive:true,force:true}))
 const db=database(t,root),sql=await readFile(new URL('../lib/charts.sql',import.meta.url),'utf8')
 const rows=[10,100].map((score,index)=>({id:`run${index}`,strategy:'characters',turns:20,forkTurns:10,soloTurns:10,
  forks:[{window:0,id:0,turns:20,scored:[[0,score,true],[10,score/2,true]],passing:[[0,score],[10,score/2]]}]}))
 const params={rows:JSON.stringify(rows)}
 const plan=(await db.query('EXPLAIN QUERY PLAN '+sql,params)).map(row=>row.detail)
 assert(plan.includes('MATERIALIZE input'),plan.join('\n'))
 assert(plan.includes('MATERIALIZE score_bounds'),plan.join('\n'))
 const [{payload}]=await db.query(sql,params),charts=JSON.parse(payload)
 assert.equal(charts.length,2)
 for(let index=0;index<charts.length;index++)for(const chart of Object.values(charts[index])){
  assert.deepEqual(chart.domains.advice.y,[0,[10,100][index]*1.05])
 }
})
