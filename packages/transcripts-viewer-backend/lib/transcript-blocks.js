import {readFile,stat} from 'node:fs/promises'

// A block is a physical source line, including blank and unfinished records.
export function createTranscriptReader() {
  const cache=new Map()
  return async path=>{
    const info=await stat(path),version=`${info.size}:${info.mtimeMs}:${info.ctimeMs}`
    if(cache.get(path)?.version===version)return cache.get(path)
    const lines=(await readFile(path,'utf8')).split('\n')
    const blocks=lines.map((raw,index)=>{
      let type='Unparsed record'
      try{const record=JSON.parse(raw);type=record?.message?.role??record?.role??record?.type??'Record'}catch{}
      return {index,type}
    })
    const result={version,lines,metadata:{total:blocks.length,blocks}}
    cache.set(path,result)
    return result
  }
}
