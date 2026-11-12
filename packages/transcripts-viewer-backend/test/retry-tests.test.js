import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {createApi} from '../server.js'

test('sample API preserves every retry tests object in numeric order with its own verbatim source',async t=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-retry-tests-'))
  const sample='windows/0/forks/0/turns/0/ts/0',expected=new Map(),rawFiles=new Map()
  for(const id of [10,0,2]){
    const path=join(root,'runs/one',sample,'attempts',String(id))
    await mkdir(path,{recursive:true})
    const tests={attempt:id,unknown:{reason:`attempt ${id}`},cases:[{index:4,status:id===10?'passed':'timeout',stdout:`  output ${id}\n\n`,extra:[1,{preserve:true}]}]}
    const raw=JSON.stringify(tests,null,id===2?4:2)+'\n'
    expected.set(id,tests);rawFiles.set(id,raw)
    await writeFile(join(path,'tests.json'),raw)
  }
  const app=createApi(root)
  t.after(async()=>{await app.close();await rm(root,{recursive:true,force:true})})
  const response=await app.inject(`/api/runs/one/${sample}`)
  assert.equal(response.statusCode,200,response.body)
  const {attempts}=response.json()
  assert.deepEqual(attempts.map(attempt=>attempt.id),[0,2,10])
  for(const attempt of attempts){
    assert.deepEqual(attempt.tests,expected.get(attempt.id),'earlier retries retain every top-level/case field')
    assert.equal(attempt.testsSource,`${sample}/attempts/${attempt.id}/tests.json`)
    const source=await app.inject(`/api/runs/one/files/${attempt.testsSource}`)
    assert.equal(source.statusCode,200)
    assert.equal(source.body,rawFiles.get(attempt.id),'each retry opens its own original JSON text')
  }
})
