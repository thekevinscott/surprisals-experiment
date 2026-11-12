export function matchFile(name = '') {
  const basename=name.split('/').at(-1).toLowerCase()
  if(basename==='transcript.jsonl')return 'transcript'
  if(basename==='solutions.json')return 'solutions'
  if(basename.endsWith('.jsonl'))return 'jsonl'
  if(basename.endsWith('.json'))return 'json'
  return 'text'
}
export function fileRoute(hash) {
  if(hash.startsWith('#files/')){
    const [path,query='']=hash.slice(7).split('?')
    const params=new URLSearchParams(query)
    params.set('name',decodeURIComponent(path))
    return params
  }
  // Existing links to physical JSONL record lines remain valid.
  if(/^#jsonl?\?/.test(hash))return new URLSearchParams(hash.slice(hash.indexOf('?')+1))
  return null
}
