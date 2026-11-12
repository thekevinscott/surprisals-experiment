// Physical records: a final newline terminates the last line, not another record.
export function transcriptLines(text) {
  if (!text) return []
  const lines = text.split('\n')
  if (lines.at(-1) === '') lines.pop()
  return lines
}
export function transcriptFile(text, source) {
  return transcriptLines(text).map((raw,index)=>{
    let role=''
    try { const record=JSON.parse(raw); role=record?.message?.role??record?.role??record?.type??'' } catch {}
    return {raw,source,role,line:index+1}
  })
}
