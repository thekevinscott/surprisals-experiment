import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,readFile,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {database} from './support/database.js'

test('summary uses an indexed sample-results join and does not aggregate costs',async t=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-summary-plan-'))
  t.after(()=>rm(root,{recursive:true,force:true}))
  const db=database(t,root),sql=await readFile(new URL('../lib/summary.sql',import.meta.url),'utf8')
  const plan=await db.query('EXPLAIN QUERY PLAN '+sql,{run:null,now:0,directories:'[]'})
  const steps=plan.map(row=>row.detail)
  assert(steps.some(step=>/SEARCH r USING AUTOMATIC.*INDEX.*turn=/.test(step)),steps.join('\n'))
  assert(!steps.some(step=>/SCAN r LEFT-JOIN/.test(step)),'sample results must not be scanned once per turn')
  assert(!steps.some(step=>/transcript_lines|cost_rows|model_costs|usage_ranked/.test(step)),'summary must not execute disabled cost queries')
})

test('chart assembly uses an indexed lookup of its materialized series',async t=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-chart-plan-'))
  t.after(()=>rm(root,{recursive:true,force:true}))
  const db=database(t,root),sql=await readFile(new URL('../lib/charts.sql',import.meta.url),'utf8')
  const plan=await db.query('EXPLAIN QUERY PLAN '+sql,{rows:'[]'})
  assert(plan.some(row=>/SEARCH x USING AUTOMATIC.*INDEX.*k=.*key=/.test(row.detail)),plan.map(row=>row.detail).join('\n'))
})
