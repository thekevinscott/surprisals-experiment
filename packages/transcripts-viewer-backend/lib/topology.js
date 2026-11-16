import {readdir} from 'node:fs/promises'
import {join} from 'node:path'

// DirSQL indexes files. Empty directories are source facts too: an in-flight
// attempt or a turn whose metadata was removed must still appear in the viewer.
export async function directories(root) {
  const paths=[]
  async function visit(path,level) {
    let entries
    try{entries=await readdir(join(root,path),{withFileTypes:true})}
    catch(error){if(error.code==='ENOENT')return;throw error}
    for(const entry of entries){
      if(!entry.isDirectory()||!/^\d+$/.test(entry.name))continue
      const child=join(path,entry.name),parts=child.split('/')
      paths.push({path:child,kind:['window','fork','turn','sample','attempt'][level],parent:parts.slice(0,-2).join('/'),window:Number(parts[1]),fork:parts[3]==null?null:Number(parts[3]),turn:parts[5]==null?null:Number(parts[5]),sample:parts[7]==null?null:Number(parts[7]),attempt:parts[9]==null?null:Number(parts[9]),position:Number(entry.name)})
      const next=['forks','turns','ts','attempts'][level]
      if(next)await visit(join(child,next),level+1)
    }
  }
  await visit('windows',0)
  return paths
}
