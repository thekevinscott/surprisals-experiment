import { stat } from 'node:fs/promises'
import { basename, dirname, join, resolve, relative } from 'node:path'

// Runs copied from a remote host retain that host's problem_dir. Resolve the
// same data-relative path against local ancestors of the experiment directory.
export async function readProblem(db, directory, problemDir) {
  if (!problemDir) return []
  const candidates = [problemDir]
  const suffix = problemDir.match(/(?:^|\/)data\/(.+)$/)?.[1]
  if (suffix) {
    let parent = resolve(directory)
    while (true) {
      candidates.push(join(parent, 'data', suffix))
      if (dirname(parent) === parent) break
      parent = dirname(parent)
    }
  }
  for (const candidate of new Set(candidates)) {
    try {await stat(candidate)}catch(error){if(error.code==='ENOENT')continue;throw error}
    const rows=await db.files(join(resolve(candidate),'{question.txt,input_output.json,solutions.json}'),{content:true})
    const files=['question.txt','input_output.json','solutions.json'].map(name=>{
      const row=rows.find(row=>basename(row.path)===name)
      return row ? {name,source:relative(directory,join(candidate,name)),text:row.content} : {name,text:null}
    })
    if (files.some(file => file.text !== null)) return files
  }
  return ['question.txt', 'input_output.json', 'solutions.json'].map(name => ({ name, text: null }))
}
