import {readdir,readFile} from 'node:fs/promises'
import {join} from 'node:path'

export async function readRunpodCosts(directory) {
  const folder=join(directory,'runpod-costs')
  const files=await readdir(folder).catch(error=>{if(error.code==='ENOENT')return [];throw error})
  return Promise.all(files.filter(name=>name.endsWith('.json')).sort().map(async name=>{
    const {id,gpu,costPerHr,start,stop}=JSON.parse(await readFile(join(folder,name),'utf8'))
    return {id,gpu,costPerHr,start,stop}
  }))
}
