import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,rm,symlink} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join,dirname} from 'node:path'
import {createApi} from '../server.js'

test('REST reads stay live, separate lazy payloads, and reject file escapes',async t=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-api-'))
  const put=async(path,value)=>{const full=join(root,path);await mkdir(dirname(full),{recursive:true});await writeFile(full,typeof value==='string'?value:JSON.stringify(value))}
  const turn='windows/0/forks/0/turns/0',base='runs/one/'
  await put(base+'run.json',{created:'2026-01-01T00:00:00Z'})
  await put(base+'settings.json',{fork_turns:10,t_samples:1,cap_strategy:'characters'})
  await put(base+turn+'/metadata.json',{advice:'advices/ab'})
  await put(base+'advices/ab/advice.json',{score:6})
  await put(base+turn+'/u/advice.txt','Advice')
  await put(base+'u/transcripts/messages.jsonl',[{role:'system',content:'system'},{role:'user',content:'question',_reset:true},{role:'assistant',content:'Advice',_complete:true}].map(JSON.stringify).join('\n'))
  await put(base+turn+'/ts/0/attempts/0/tests.json',{passed:1,total:1,all_passed:true})
  const app=createApi(root);t.after(async()=>{await app.close();await rm(root,{recursive:true,force:true})})
  const get=async url=>{const r=await app.inject(url);assert.equal(r.statusCode,200,r.body);return r.json()}
  assert.equal((await get('/api/runs')).rows[0].best,6)
  assert.equal((await get('/api/runs/index')).rows[0].id,'one')
  assert.equal((await get('/api/runs/one/summary')).row.best,6)
  const fork=(await get('/api/runs/one')).diagram[0].forks[0]
  assert.equal('messages' in fork,false)
  assert.equal('attempts' in fork.parallel[0].samples[0],false)
  assert.equal((await get('/api/runs/one/'+turn+'/transcript')).messages.length,3)
  assert.equal((await get('/api/runs/one/'+turn+'/ts/0')).attempts[0].tests.all_passed,true)
  await put(base+turn+'/ts/0/attempts/1/generation.json',{timed_out:true})
  assert.equal((await get('/api/runs')).rows[0].best,null,'latest timeout supersedes earlier passing tests')
  assert.equal((await get('/api/runs/one/'+turn+'/ts/0')).attempts[1].generation.timed_out,true)
  await put('runs/two/run.json',{created:'2026-01-01T00:00:00Z'})
  assert.equal((await get('/api/runs')).rows.length,2,'new runs appear without restart')
  await put(base+turn+'/u/advice.txt','Updated advice')
  const raw=await app.inject('/api/runs/one/files/'+turn+'/u/advice.txt')
  assert.equal(raw.body,'Updated advice');assert.match(raw.headers['content-type'],/text\/plain/);assert.equal(raw.headers['cache-control'],'no-store')
  await put('secret','private');await symlink(join(root,'secret'),join(root,base,'escape'))
  for(const url of ['/api/runs/one/files/escape','/api/runs/one/files/%2e%2e/%2e%2e/secret','/api/runs/%2e%2e/files/secret'])assert.notEqual((await app.inject(url)).statusCode,200,url)
  assert.equal((await app.inject('/api/runs/absent')).statusCode,404)
  await put('runs/broken/run.json',{created:'2026-01-01T00:00:00Z'})
  await put('runs/broken/windows/0/forks/0/turns/0/metadata.json','{incomplete')
  assert.equal((await get('/api/runs/index')).rows.length,3,'index avoids reading turn artifacts')
  assert.equal((await get('/api/runs/one/summary')).row.id,'one','one run does not depend on other runs')
})
