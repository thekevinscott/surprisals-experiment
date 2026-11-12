// Keep every source record and its physical line; no context slicing in a file view.
export function transcriptFile(text, source) {
  return text.split('\n').flatMap((raw,index)=>{
    let role='Unparsed record'
    try{const record=JSON.parse(raw);role=record?.message?.role??record?.role??record?.type??'Record'}catch{}
    return [{raw,source,role,line:index+1}]
  })
}

export function transcriptContent(raw) {
  try {
    const record=JSON.parse(raw)
    const content=(record.message ?? record).content
    return typeof content === 'string' ? content : content == null ? '' : JSON.stringify(content,null,2)
  } catch { return '' }
}
export function transcriptMetadata(raw) {
  try {
    const record=JSON.parse(raw)
    const {role,content,message,...metadata}=record
    if (message) {
      const {role,content,...fields}=message
      if (Object.keys(fields).length) metadata.message=fields
    }
    return Object.keys(metadata).length ? metadata : undefined
  } catch { return undefined }
}
