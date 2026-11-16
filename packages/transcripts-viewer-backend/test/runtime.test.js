import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,utimes,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {createApi} from '../server.js'

test('API runtime sums invocations, excludes gaps, uses the lost invocation stderr and advances live',async t=>{
 const root=await mkdtemp(join(tmpdir(),'viewer-runtime-')),run=join(root,'runs/one')
 await mkdir(run,{recursive:true})
 const meta={created:'2026-11-01T00:00:00Z',invocations:[
  {started:'2026-11-01T00:00:00Z',ended:'2026-11-01T01:00:00Z'},
  {started:'2026-11-01T03:00:00Z',ended:'2026-11-01T04:30:00Z'},
  {started:'2026-11-01T06:00:00Z',ended:'2026-11-01T12:00:00Z',ended_by:'lost',stderr:'stderr-lost.txt'},
  {started:'2026-11-01T13:00:00Z',stderr:'stderr-open.txt'},
 ]}
 await writeFile(join(run,'run.json'),JSON.stringify(meta))
 await writeFile(join(run,'stderr-lost.txt'),'last activity')
 await utimes(join(run,'stderr-lost.txt'),new Date('2026-11-01T06:20:00Z'),new Date('2026-11-01T06:20:00Z'))
 await writeFile(join(run,'stderr-open.txt'),'new invocation')
 await utimes(join(run,'stderr-open.txt'),new Date('2026-11-01T13:59:00Z'),new Date('2026-11-01T13:59:00Z'))
 let now=Date.parse('2026-11-01T14:00:00Z')
 t.mock.method(Date,'now',()=>now)
 const app=createApi(root)
 t.after(async()=>{await app.close();await rm(root,{recursive:true,force:true})})
 const get=async()=>{const response=await app.inject('/api/runs/one/details');assert.equal(response.statusCode,200,response.body);return response.json().row}
 assert.equal((await get()).elapsed,13800,'3600 + 5400 + 1200 + 3600 seconds')
 now+=1000
 assert.equal((await get()).elapsed,13801)
 meta.invocations[3].ended='2026-11-01T14:00:00Z'
 await writeFile(join(run,'run.json'),JSON.stringify(meta))
 now+=3600000
 assert.equal((await get()).elapsed,13800,'completed runs stop ticking')
 await rm(join(run,'stderr-lost.txt'))
 assert.equal((await get()).elapsed,null,'missing lost-invocation evidence must not count the delayed relaunch timestamp')
})

test('legacy run without invocations uses created and ended',async t=>{
 const root=await mkdtemp(join(tmpdir(),'viewer-runtime-legacy-')),run=join(root,'runs/one')
 await mkdir(run,{recursive:true})
 await writeFile(join(run,'run.json'),JSON.stringify({created:'2026-11-01T00:00:00Z',ended:'2026-11-01T01:00:00Z'}))
 const app=createApi(root)
 t.after(async()=>{await app.close();await rm(root,{recursive:true,force:true})})
 const response=await app.inject('/api/runs/one/details')
 assert.equal(response.statusCode,200,response.body)
 assert.equal(response.json().row.elapsed,3600)
})
