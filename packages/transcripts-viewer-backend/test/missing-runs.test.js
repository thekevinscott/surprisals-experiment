import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,rm,access} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {spawn} from 'node:child_process'
import {createServer} from 'node:net'
import {once} from 'node:events'
import {createApi} from '../server.js'

test('missing runs is empty, and the same live connection sees creation, deletion and recreation', {timeout:20000}, async t=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-no-runs-')),app=createApi(root),controller=new AbortController()
  t.after(async()=>{controller.abort();await app.close();await rm(root,{recursive:true,force:true})})
  for(const url of ['/api/runs','/api/runs/index']){
    const response=await app.inject(url)
    assert.equal(response.statusCode,200,response.body)
    assert.deepEqual(response.json().rows,[])
  }
  await assert.rejects(access(join(root,'runs')),{code:'ENOENT'},'reads must not create the directory')
  const base=await app.listen({host:'127.0.0.1',port:0})
  const response=await fetch(base+'/api/events',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({resources:['/api/runs','/api/runs/index']}),signal:controller.signal})
  const reader=response.body.getReader(),decoder=new TextDecoder();let buffer=''
  async function expectRows(ids){
    const seen=new Set()
    while(seen.size<2){
      let end=buffer.indexOf('\n\n')
      if(end<0){const chunk=await reader.read();assert.equal(chunk.done,false);buffer+=decoder.decode(chunk.value,{stream:true});continue}
      const frame=buffer.slice(0,end);buffer=buffer.slice(end+2)
      assert(!frame.startsWith('event: stream-error'),frame)
      if(!frame.startsWith('event: resource\n'))continue
      const {url,data}=JSON.parse(frame.split('\ndata: ')[1]);assert.deepEqual(data.rows.map(row=>row.id),ids);seen.add(url)
    }
  }
  const putRun=async id=>{const folder=join(root,'runs',id);await mkdir(folder,{recursive:true});await writeFile(join(folder,'run.json'),JSON.stringify({created:'2026-01-01'}))}
  await expectRows([])
  await putRun('one');await expectRows(['one'])
  await rm(join(root,'runs'),{recursive:true});await expectRows([])
  await putRun('two');await expectRows(['two'])
})

test('CLI starts with no runs directory and serves an empty dashboard', {timeout:20000}, async t=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-no-runs-cli-'))
  const reservation=createServer();await new Promise(resolve=>reservation.listen(0,'127.0.0.1',resolve));const port=reservation.address().port;await new Promise(resolve=>reservation.close(resolve))
  const child=spawn(process.execPath,[new URL('../../transcripts-viewer-frontend/bin/transcripts-viewer.js',import.meta.url).pathname,root,'--port',String(port)],{stdio:['ignore','pipe','pipe']})
  const exited=once(child,'exit');let output=''
  t.after(async()=>{if(child.exitCode===null&&child.signalCode===null)child.kill('SIGTERM');await exited;await rm(root,{recursive:true,force:true})})
  await new Promise((resolve,reject)=>{child.stdout.on('data',chunk=>{output+=chunk;if(output.includes('Viewer:'))resolve()});child.stderr.on('data',chunk=>{output+=chunk});child.once('exit',()=>reject(Error(output)));child.once('error',reject)})
  const response=await fetch(`http://127.0.0.1:${port}/api/runs`)
  assert.equal(response.status,200);assert.deepEqual((await response.json()).rows,[])
  assert.equal((await fetch(`http://127.0.0.1:${port}/`)).status,200)
  await assert.rejects(access(join(root,'runs')),{code:'ENOENT'})
})
