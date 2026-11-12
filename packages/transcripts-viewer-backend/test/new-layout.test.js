import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp, mkdir, readFile, writeFile, rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {dirname, join} from 'node:path'
import {readRunDiagram, readTurnTranscript} from '../lib/experiment.js'
import {transcriptFile} from '../../transcripts-viewer-frontend/src/composables/transcriptFile.js'

test('fork zero links shared advice and retains rejected turns and exact transcript text', async t => {
  const root=await mkdtemp(join(tmpdir(),'viewer-layout-'))
  t.after(()=>rm(root,{recursive:true,force:true}))
  const put=async(path,value)=>{await mkdir(dirname(join(root,path)),{recursive:true});await writeFile(join(root,path),typeof value==='string'?value:JSON.stringify(value))}
  const rejected=await readFile(new URL('../../../surprisals_experiment/src/surprisals_experiment/prompts/u/rejected.txt',import.meta.url),'utf8')
  const fork='windows/0/forks/0', source=fork+'/u/transcript.jsonl'
  const records=[{role:'user',content:rejected}, {role:'system',content:'system'},
    {role:'user',content:'question',_attempt:0}, {role:'assistant',content:'too long',_complete:true},
    {role:'user',content:rejected}, {role:'assistant',content:'accepted',_complete:true},
    {role:'system',content:'system'}, {role:'user',content:'next',_attempt:1},
    {role:'user',content:rejected+' '}, {role:'assistant',content:'partial',_complete:false},
    {role:'user',content:rejected}, {role:'user',content:rejected}]
  const text=records.map(JSON.stringify).join('\n\n')+'\n\n{"incomplete":'
  await put(source,text)
  await put('windows/0/window.json',{})
  await put(fork+'/fork.json',{})
  await put(fork+'/turns/0/metadata.json',{advice:'advices/abc'})
  await mkdir(join(root,fork,'turns/1'),{recursive:true}) // scorer deleted metadata
  await put(fork+'/turns/2/metadata.json',{advice:null,error:'output limit'})
  await put('advices/abc/advice.txt','accepted\r\n')
  await put('advices/abc/advice.json',{score:9,tokens:[['accepted',9]]})
  const [window]=await readRunDiagram(root,{cap_strategy:'surprisal'})
  const [first,second,third]=window.forks[0].parallel
  assert.equal(window.forks[0].transcriptPath,source)
  assert.equal(first.advice,'accepted\r\n')
  assert.equal(first.adviceSource,'advices/abc/advice.txt')
  assert.equal(first.measurement,9)
  assert.deepEqual(first.tokens,[['accepted',9]])
  assert.equal(first.rejections,1)
  assert.equal(second.rejections,2)
  assert.equal(second.advice,null)
  assert.equal(third.error,'output limit')
  for(const turn of [0,1,2]) {
    const messages=await readTurnTranscript(root,0,0,turn)
    assert.equal(messages.map(m=>m.raw).join('\n'),text)
    assert.deepEqual(messages.map(m=>m.line),text.split('\n').map((_,i)=>i+1))
  }
  assert.equal(transcriptFile(await readFile(join(root,source),'utf8'),source).map(m=>m.raw).join('\n'),text)
})
