import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,rm,symlink} from 'node:fs/promises'
import {join,dirname} from 'node:path'
import {tmpdir} from 'node:os'
import {createApi} from '../server.js'

async function stream(base,path,t) {
  const controller=new AbortController()
  t.after(()=>controller.abort())
  const response=await fetch(base+path,{headers:{Accept:'text/event-stream'},signal:controller.signal})
  assert.equal(response.status,200,await (response.status===200?'':response.text()))
  assert.match(response.headers.get('content-type'),/text\/event-stream/)
  const reader=response.body.getReader(),decoder=new TextDecoder()
  let buffer=''
  return {close:()=>controller.abort(),async next(type='data'){
    const timeout=setTimeout(()=>controller.abort(),6000)
    try {
      while(true){
        const boundary=buffer.indexOf('\n\n')
        if(boundary>=0){
          const frame=buffer.slice(0,boundary);buffer=buffer.slice(boundary+2)
          if(frame.startsWith(`event: ${type}\n`))return JSON.parse(frame.split('\ndata: ')[1])
          continue
        }
        const chunk=await reader.read()
        if(chunk.done)throw Error('Stream ended')
        buffer+=decoder.decode(chunk.value,{stream:true})
      }
    }finally{clearTimeout(timeout)}
  }}
}

test('every data endpoint streams snapshots, live changes, missing files and recovery', {timeout:20000}, async t=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-events-')),problem=await mkdtemp(join(tmpdir(),'viewer-problem-'))
  const put=async(path,value)=>{await mkdir(dirname(path),{recursive:true});await writeFile(path,typeof value==='string'?value:JSON.stringify(value))}
  const run=join(root,'runs/one'),turn='windows/0/forks/0/turns/0',attempt=turn+'/ts/0/attempts/0'
  await put(join(run,'run.json'),{created:'2026-01-01'})
  await put(join(run,'settings.json'),{problem_dir:problem,t_samples:1,fork_turns:10})
  await put(join(run,turn,'metadata.json'),{advice:'advices/ab'})
  await put(join(run,'advices/ab/advice.json'),{score:3})
  await put(join(run,turn,'u/advice.txt'),'old')
  await put(join(run,'u/transcripts/messages.jsonl'),'{"role":"assistant","content":"old","_complete":true}')
  await put(join(run,attempt,'tests.json'),{passed:1,total:1,all_passed:true})
  await put(join(problem,'question.txt'),'old question')
  const app=createApi(root)
  t.after(async()=>{await app.close();await rm(root,{recursive:true});await rm(problem,{recursive:true})})
  const base=await app.listen({host:'127.0.0.1',port:0})
  const urls=['/api/runs','/api/runs/index','/api/runs/one/summary','/api/runs/one',`/api/runs/one/${turn}/transcript`,`/api/runs/one/${turn}/ts/0`,`/api/runs/one/files/${turn}/u/advice.txt`,'/api/runs/one/problem/question.txt']
  const streams=[]
  for(const url of urls){
    const s=await stream(base,url,t);streams.push(s)
    const expected=await fetch(base+url)
    assert.deepEqual(await s.next(),url.includes('/files/')||url.includes('/problem/')?await expected.text():await expected.json(),url)
  }
  const changes=await stream(base,'/api/events?resources='+encodeURIComponent(JSON.stringify(['/api/runs/index'])),t)
  assert.equal((await changes.next('resource')).data.rows.length,1)
  // Same-size replacement and new nested files both need to be observed.
  await put(join(run,turn,'u/advice.txt'),'new')
  await put(join(run,'u/transcripts/messages.jsonl'),'{"role":"assistant","content":"new","_complete":true}')
  await put(join(run,'advices/ab/advice.json'),{score:1})
  await put(join(run,attempt,'tests.json'),{passed:0,total:1,all_passed:false})
  await put(join(run,'run.json'),{created:'2026-01-01',params:{'cap-strategy':'changed'}})
  await put(join(problem,'question.txt'),'new question')
  const updates=await Promise.all(streams.map(s=>s.next()))
  assert.equal(updates[0].rows[0].strategy,'changed')
  assert.equal(updates[1].rows[0].strategy,'changed')
  assert.equal(updates[2].row.best,null)
  assert.equal(updates[3].diagram[0].forks[0].parallel[0].advice,'new')
  assert.match(updates[4].messages[0].raw,/new/)
  assert.equal(updates[5].attempts[0].tests.all_passed,false)
  assert.equal(updates[6],'new')
  assert.equal(updates[7],'new question')
  assert.equal((await changes.next('resource')).data.rows[0].strategy,'changed')
  await rm(join(run,turn,'u/advice.txt'))
  assert.equal((await streams[6].next('stream-error')).status,404)
  await put(join(run,turn,'u/advice.txt'),'restored')
  assert.equal(await streams[6].next(),'restored')
  await put(join(root,'runs/two/run.json'),{created:'2026-01-01'})
  let index=await streams[1].next()
  while(index.rows.length<2)index=await streams[1].next()
  assert.equal(index.rows.length,2)
  await symlink(join(problem,'question.txt'),join(run,'escape'))
  assert.equal((await fetch(base+'/api/runs/one/files/escape',{headers:{Accept:'text/event-stream'}})).status,400)
  for(const s of streams)s.close()
  changes.close()
})
