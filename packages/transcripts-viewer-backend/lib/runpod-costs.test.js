import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {createApi} from '../server.js'
test('pod costs are experiment-wide, disk-only, and absent until recorded',async()=>{
  const root=await mkdtemp(join(tmpdir(),'runpod-costs-')),app=createApi(root)
  try {
    assert.deepEqual((await app.inject('/api/runs/runpod-costs')).json(),[])
    await mkdir(join(root,'runpod-costs'))
    const pod={id:'pod1',gpu:'H100',costPerHr:2.5,start:'2026-11-13T00:00:00Z',stop:null}
    await writeFile(join(root,'runpod-costs/pod1.json'),JSON.stringify({...pod,env:{secret:'never expose'}}))
    assert.deepEqual((await app.inject('/api/runs/runpod-costs')).json(),[pod])
    pod.stop='2026-11-13T02:00:00Z'
    await writeFile(join(root,'runpod-costs/pod1.json'),JSON.stringify(pod))
    assert.deepEqual((await app.inject('/api/runs/runpod-costs')).json(),[pod])
  } finally {await app.close();await rm(root,{recursive:true,force:true})}
})
