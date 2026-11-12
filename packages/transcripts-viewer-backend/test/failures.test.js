import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises'
import {join,dirname} from 'node:path'
import {tmpdir} from 'node:os'
import {readRunDiagram,readSample} from '../lib/experiment.js'
async function fixture(t, files) {
 const root=await mkdtemp(join(tmpdir(),'viewer-failures-'));t.after(()=>rm(root,{recursive:true,force:true}));
 for(const [path,value] of Object.entries(files)){await mkdir(dirname(join(root,path)),{recursive:true});await writeFile(join(root,path),typeof value==='string'?value:JSON.stringify(value))}return root
}
test('failed U turn retains recorded output-token-limit reason',async t=>{
 const reason='U hit its output token limit (131072 completion tokens, 131072 reasoning tokens)'
 const root=await fixture(t,{'windows/0/forks/2/turns/8/metadata.json':{advice:null,error:reason}})
 const d=await readRunDiagram(root,{fork_turns:10});assert.equal(d[0].forks[0].parallel[0].error,reason)
})
test('T attempts remain separate, numerically ordered, with timeout, tests and files',async t=>{
 const base='windows/0/forks/1/turns/5/ts/1/attempts/'
 const root=await fixture(t,{
  [base+'0/generation.json']:{timed_out:true},[base+'0/src/partial.py']:'partial',
  [base+'1/tests.json']:{passed:12,total:12,all_passed:true},[base+'1/src/main.py']:'solution',
  [base+'10/generation.json']:{timed_out:true},
 })
 const d=await readRunDiagram(root,{fork_turns:10});const sample=await readSample(join(root,d[0].forks[0].parallel[0].samples[0].source),root)
 assert.deepEqual(sample.attempts.map(a=>a.id),[0,1,10]);assert.equal(sample.attempts[0].generation.timed_out,true)
 assert.equal(sample.attempts[0].files[0].name,'partial.py');assert.equal(sample.attempts[1].tests.passed,12)
 assert.equal(sample.attempts[2].generation.timed_out,true)
})
