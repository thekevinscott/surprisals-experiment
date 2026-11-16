import {readFileSync} from 'node:fs'
import {stat} from 'node:fs/promises'
import {join} from 'node:path'

const sql=readFileSync(new URL('./runtime.sql',import.meta.url),'utf8')
export async function runRuntime(directory,meta,database,now=Date.now()) {
  const stderr={}
  for(const invocation of meta.invocations?.length?meta.invocations:[meta]){
    if(invocation.ended_by!=='lost'||!invocation.stderr)continue
    try{stderr[invocation.stderr]=(await stat(join(directory,invocation.stderr))).mtimeMs}
    catch(error){if(error.code!=='ENOENT')throw error}
  }
  const [runtime]=await database.query(sql,{meta:JSON.stringify(meta),stderr:JSON.stringify(stderr),now})
  return runtime
}
