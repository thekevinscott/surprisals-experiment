export function matchFile(name = '') {
  const basename=name.split('/').at(-1).toLowerCase()
  if(basename==='transcript.jsonl')return 'transcript'
  if(basename==='solutions.json')return 'solutions'
  if(basename.endsWith('.jsonl'))return 'jsonl'
  if(basename.endsWith('.json'))return 'json'
  if(basename.endsWith('.py'))return 'python'
  return 'text'
}
