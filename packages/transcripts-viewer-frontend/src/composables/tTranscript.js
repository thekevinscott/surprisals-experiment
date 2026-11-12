export function tTranscript(text, source) {
  return text.split('\n').flatMap((raw, index) => {
    if (!raw.trim()) return []
    try { const record=JSON.parse(raw);return record.type==='message' ? [{role:record.message?.role ?? 'Record',raw,source,line:index+1}] : [] }
    catch { return [{role:'Unparsed record',raw,source,line:index+1}] }
  })
}
