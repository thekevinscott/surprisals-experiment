import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {createApi} from '../server.js'

test('one POST stream accepts a growing run with more than 256 distinct resources',async t=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-large-stream-'))
  await mkdir(join(root,'runs/one'),{recursive:true})
  const resources=Array.from({length:300},(_,i)=>`/api/runs/one/files/block-${i}.txt`)
  await Promise.all(resources.map((_,i)=>writeFile(join(root,`runs/one/block-${i}.txt`),String(i))))
  const app=createApi(root),controller=new AbortController()
  t.after(async()=>{controller.abort();await app.close();await rm(root,{recursive:true,force:true})})
  const base=await app.listen({host:'127.0.0.1',port:0})
  const response=await fetch(base+'/api/events',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({resources}),signal:controller.signal})
  assert.equal(response.status,200)
  const reader=response.body.getReader(),decoder=new TextDecoder(),seen=new Set()
  let buffer=''
  while(seen.size<resources.length){
    const {value,done}=await reader.read();assert.equal(done,false);buffer+=decoder.decode(value,{stream:true})
    let boundary
    while((boundary=buffer.indexOf('\n\n'))>=0){
      const frame=buffer.slice(0,boundary);buffer=buffer.slice(boundary+2)
      if(!frame.startsWith('event: resource\n'))continue
      const {url,data}=JSON.parse(frame.split('\ndata: ')[1]);seen.add(url)
      assert.equal(data,String(resources.indexOf(url)))
    }
  }
  assert.equal(seen.size,300)
  controller.abort()
  const invalid=await app.inject({method:'POST',url:'/api/events',payload:{resources:['/private']}})
  assert.equal(invalid.statusCode,400)
})
