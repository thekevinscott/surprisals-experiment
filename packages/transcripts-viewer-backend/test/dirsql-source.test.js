import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,writeFile,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {DirSQL} from 'dirsql'

test('named-table queries do not re-ingest unchanged files',async()=>{
  const root=await mkdtemp(join(tmpdir(),'viewer-dirsql-source-'))
  await writeFile(join(root,'fact.json'),'{}')
  let reads=0
  const db=new DirSQL({root,tables:[{name:'facts',ddl:'CREATE TABLE facts (value INTEGER)',glob:'*.json',onFile:()=>{reads++;return [{value:1}]}}]})
  try{
    await db.ready
    const initial=reads
    assert.equal(initial,1)
    for(let i=0;i<3;i++)assert.deepEqual(await db.query('SELECT sum(value) AS total FROM facts'),[{total:1}])
    assert.equal(reads,initial)
  }finally{db.close();await rm(root,{recursive:true,force:true})}
})
