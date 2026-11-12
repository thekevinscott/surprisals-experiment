import {realpath,stat,readdir,readFile} from 'node:fs/promises'
import {resolve,relative,isAbsolute} from 'node:path'
export async function runFile(root, path) {
  const base=await realpath(root), target=await realpath(resolve(base,path)), rel=relative(base,target)
  if(rel==='..'||rel.startsWith('../')||isAbsolute(rel))throw new Error('Path outside run')
  return target
}
export async function sourceBytes(path) {
  return (await stat(path)).isDirectory() ? Buffer.from((await readdir(path)).sort().join('\n')+'\n') : readFile(path)
}
