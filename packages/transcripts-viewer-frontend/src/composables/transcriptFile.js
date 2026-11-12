// Keep every source record and its physical line; no context slicing in a file view.
export function transcriptFile(text, source) {
  return text.split('\n').flatMap((raw,index)=>{
    let role='Unparsed record'
    try{const record=JSON.parse(raw);role=record?.message?.role??record?.role??record?.type??'Record'}catch{}
    return [{raw,source,role,line:index+1}]
  })
}
