import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,mkdir,writeFile,symlink,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {runFile} from '../lib/run-files.js'
test('run file paths cannot escape via traversal or symlink',async t=>{
 const root=await mkdtemp(join(tmpdir(),'viewer-path-'));t.after(()=>rm(root,{recursive:true,force:true}));await mkdir(join(root,'run'));await writeFile(join(root,'secret'),'secret');await writeFile(join(root,'run','ok.txt'),'ok');await symlink(join(root,'secret'),join(root,'run','link'))
 assert.equal(await runFile(join(root,'run'),'ok.txt'),join(root,'run','ok.txt'))
 await assert.rejects(runFile(join(root,'run'),'../secret'));await assert.rejects(runFile(join(root,'run'),'link'))
})
