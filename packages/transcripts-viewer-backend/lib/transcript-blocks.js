import {readFile} from 'node:fs/promises'

// A block is a physical source line, including blank and unfinished records.
export function createTranscriptReader() {
  return async path=>{
    const text=await readFile(path,'utf8')
    const lines=text.split('\n')
    if(lines.at(-1)==='')lines.pop()
    const blocks=lines.map((raw,index)=>{
      let type=''
      try{const record=JSON.parse(raw);type=record?.message?.role??record?.role??record?.type??''}catch{}
      return {index,type}
    })
    return {lines,metadata:{total:blocks.length,blocks}}
  }
}
