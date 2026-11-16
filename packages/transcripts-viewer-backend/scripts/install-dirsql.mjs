import {execFileSync} from 'node:child_process'
import {existsSync,readFileSync} from 'node:fs'
import {fileURLToPath} from 'node:url'
import {join} from 'node:path'

const root=fileURLToPath(new URL('../',import.meta.url))
const {dirsqlSource:{repository,commit}}=JSON.parse(readFileSync(join(root,'package.json'),'utf8'))
const source=join(root,'.dirsql-source')
const run=(command,args,cwd=source)=>execFileSync(command,args,{cwd,stdio:'inherit'})
if(!existsSync(source))run('git',['clone','--no-checkout',repository,source],root)
run('git',['fetch','--depth','1','origin',commit])
run('git',['checkout','--detach',commit])
const packageRoot=join(source,'packages/ts')
run('pnpm',['install','--frozen-lockfile'],packageRoot)
run('pnpm',['run','build'],packageRoot)
