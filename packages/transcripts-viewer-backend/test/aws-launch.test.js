/* Costs disabled for now.
import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {runSummary} from '../lib/experiment.js'
import {database} from './support/database.js'
import {eventually} from './support/eventually.js'
test('run summary reads earliest valid launch from stderr and leaves missing launches unknown',async t=>{
 const root=await mkdtemp(join(tmpdir(),'viewer-aws-')),run=join(root,'runs/one')
 t.after(()=>rm(root,{recursive:true,force:true}))
 await mkdir(run,{recursive:true})
 await writeFile(join(run,'run.json'),JSON.stringify({started:'2026-11-13T00:00:00Z'}))
 const db=database(t,root)
 assert.equal((await runSummary(db,'one')).awsLaunched,null)
 await writeFile(join(run,'stderr-a.txt'),'noise\ninvalid instance launched\n2026-11-13T01:02:03+00:00 instance launched\n2026-11-13T01:03:00+00:00 instance running\n')
 await writeFile(join(run,'stderr-b.txt'),'2026-11-13T00:02:03+00:00 instance launched\n')
 await eventually(async()=>assert.equal((await runSummary(db,'one')).awsLaunched,'2026-11-13T00:02:03.000Z'))
})
*/
