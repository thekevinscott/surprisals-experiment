import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,rm,symlink} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {createApi} from '../server.js'

test('transcript metadata omits contents and ranges preserve every original physical line',async t=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-transcript-blocks-'))
  const run=join(root,'runs','one'),source='u/transcript.jsonl'
  await mkdir(join(run,'u'),{recursive:true})
  const lines=['{"role":"system","content":"first"}\r','  ','{"role":"system","content":"first","_reset":true}','{"message":{"role":"assistant","content":"partial"},"_complete":false}','{"type":"provider_error","error":"failure"}','{"role":','']
  await writeFile(join(run,source),lines.join('\n'))
  const app=createApi(root)
  t.after(async()=>{await app.close();await rm(root,{recursive:true,force:true})})
  const get=async url=>{const response=await app.inject(url);assert.equal(response.statusCode,200,response.body);return response.json()}
  const metadata='/api/runs/one/transcripts/'+source
  assert.deepEqual(await get(metadata),{total:7,blocks:['system','Unparsed record','system','assistant','provider_error','Unparsed record','Unparsed record'].map((type,index)=>({index,type}))})
  const blocks=[]
  for(const [start,end] of [[0,2],[2,5],[5,7]]){
    const result=await get(`/api/runs/one/transcript-blocks/${start}/${end}/${source}`)
    assert.deepEqual(result,{blocks:lines.slice(start,end).map((raw,offset)=>({index:start+offset,raw}))})
    blocks.push(...result.blocks)
  }
  assert.equal(blocks.map(block=>block.raw).join('\n'),lines.join('\n'))
  await writeFile(join(run,source),lines.join('\n')+'new record')
  assert.deepEqual(await get(`/api/runs/one/transcript-blocks/6/7/${source}`),{blocks:[{index:6,raw:'new record'}]},'content remains live when a partial record changes')
  await writeFile(join(run,source),lines.join('\n')+'new record\n')
  assert.equal((await get(metadata)).total,8,'metadata sees appended lines')
  assert.deepEqual(await get(`/api/runs/one/transcript-blocks/8/12/${source}`),{blocks:[]})
  for(const range of ['-1/2','2/1','0/1.5','x/2'])assert.equal((await app.inject(`/api/runs/one/transcript-blocks/${range}/${source}`)).statusCode,400)
  await writeFile(join(root,'secret'),'secret')
  await symlink(join(root,'secret'),join(run,'escape'))
  for(const endpoint of ['transcripts','transcript-blocks/0/1'])assert.notEqual((await app.inject(`/api/runs/one/${endpoint}/escape`)).statusCode,200)
})
