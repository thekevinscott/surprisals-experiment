import {readFile,stat} from 'node:fs/promises'

// A block is a physical source line, including blank and unfinished records.
export function createTranscriptReader() {
  const cache=new Map()
  return async path=>{
    const info=await stat(path),version=`${info.size}:${info.mtimeMs}:${info.ctimeMs}`
    if(cache.get(path)?.version===version)return cache.get(path)
    const text=await readFile(path,'utf8')
    const lines=text.split('\n')
    if(lines.at(-1)==='')lines.pop()
    const blocks=lines.map((raw,index)=>{
      let type=''
      try{const record=JSON.parse(raw);type=record?.message?.role??record?.role??record?.type??''}catch{}
      return {index,type}
    })
    const result={version,lines,metadata:{total:blocks.length,blocks}}
    cache.set(path,result)
    return result
  }
}
