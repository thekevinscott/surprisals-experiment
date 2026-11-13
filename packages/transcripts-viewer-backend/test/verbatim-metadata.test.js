import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join,dirname} from 'node:path'
import {createApi} from '../server.js'

test('turn and advice display retain parsed metadata, arbitrary advice names and all token units',async t=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-verbatim-metadata-'))
  const run=join(root,'runs/one'),turn='windows/0/forks/0/turns/0'
  const put=async(path,value)=>{await mkdir(dirname(join(run,path)),{recursive:true});await writeFile(join(run,path),typeof value==='string'?value:JSON.stringify(value))}
  const metadata={advice:'advices/non-hex-name',custom:{key:'unchanged'},error:null,rejections:8}
  const scored={score:1234.567,tokens:[['answer',3.75]],unit:'characters',details:{all:true},unknown:[1,2]}
  await put('settings.json',{cap_strategy:'characters'})
  await put(turn+'/metadata.json',metadata)
  await put(metadata.advice+'/advice.txt','answer\n')
  await put(metadata.advice+'/advice.json',scored)
  const app=createApi(root)
  t.after(async()=>{await app.close();await rm(root,{recursive:true,force:true})})
  const response=await app.inject('/api/runs/one');assert.equal(response.statusCode,200,response.body)
  const actual=response.json().diagram[0].forks[0].parallel[0]
  assert.deepEqual(actual.metadata,metadata)
  assert.deepEqual(actual.adviceMetadata,scored)
  assert.equal(actual.advice,'answer\n')
  assert.deepEqual(actual.tokens,scored.tokens)
  assert.equal(actual.measurement,scored.score)
  assert.equal('rejections' in actual,false,'no prompt-matched count is invented')
  assert.equal((await app.inject(`/api/runs/one/${turn}/transcript`)).statusCode,404,'removed reconstructed endpoint stays unavailable')
})
