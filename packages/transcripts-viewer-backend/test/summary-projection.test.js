import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,readFile,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {database} from './support/database.js'

test('dashboard does not fetch advice bodies into its materialized turn rows',async t=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-summary-projection-'))
  t.after(()=>rm(root,{recursive:true,force:true}))
  const db=database(t,root),sql=await readFile(new URL('../lib/summary.sql',import.meta.url),'utf8')
  const plan=await db.query('EXPLAIN QUERY PLAN '+sql,{run:null,now:0,directories:'[]'})
  // Every turn may reuse a large advice body. Fetching it here copies it into
  // turns, evaluated and scored even though no dashboard field displays it.
  assert(plan.some(row=>/USING COVERING INDEX advice_text_advice/.test(row.detail)),plan.map(row=>row.detail).join('\n'))
})
