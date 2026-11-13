import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,writeFile,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {runSummary} from '../lib/experiment.js'
test('run summary reads earliest valid launch from stderr and leaves missing launches unknown',async t=>{
 const root=await mkdtemp(join(tmpdir(),'viewer-aws-'))
 t.after(()=>rm(root,{recursive:true,force:true}))
 await writeFile(join(root,'run.json'),JSON.stringify({started:'2026-11-13T00:00:00Z'}))
 assert.equal((await runSummary(root)).awsLaunched,null)
 await writeFile(join(root,'stderr-a.txt'),'noise\ninvalid instance launched\n2026-11-13T01:02:03+00:00 instance launched\n2026-11-13T01:03:00+00:00 instance running\n')
 await writeFile(join(root,'stderr-b.txt'),'2026-11-13T00:02:03+00:00 instance launched\n')
 assert.equal((await runSummary(root)).awsLaunched,'2026-11-13T00:02:03.000Z')
})
