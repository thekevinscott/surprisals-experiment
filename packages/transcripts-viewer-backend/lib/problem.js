import { readFile } from 'node:fs/promises'
import { dirname, join, resolve, relative } from 'node:path'

// Runs copied from a remote host retain that host's problem_dir. Resolve the
// same data-relative path against local ancestors of the experiment directory.
export async function readProblem(directory, problemDir) {
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
    const files = await Promise.all(['question.txt', 'input_output.json', 'solutions.json'].map(async name => {
      try { return { name, source: relative(directory, join(candidate, name)), text: await readFile(join(candidate, name), 'utf8') } }
      catch (error) { if (error.code === 'ENOENT') return { name, text: null }; throw error }
    }))
    if (files.some(file => file.text !== null)) return files
  }
  return ['question.txt', 'input_output.json', 'solutions.json'].map(name => ({ name, text: null }))
}
