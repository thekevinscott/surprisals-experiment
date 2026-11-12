import Fastify from 'fastify'
import {createReadStream} from 'node:fs'
import {readFile,stat} from 'node:fs/promises'
import {join,resolve} from 'node:path'
import {readExperiment,readRunIndex,runSummary,readRunDiagram,readTurnTranscript,readSample} from './lib/experiment.js'
import {readProblem} from './lib/problem.js'
import {runFile,sourceBytes} from './lib/run-files.js'

export function createApi(directory) {
  directory = resolve(directory)
  const app = Fastify()
  app.addHook('onRequest', async (_request, reply) => { reply.header('Cache-Control','no-store') })
  app.setErrorHandler((error,_request,reply) => {
    reply.code(error.statusCode ?? (error.code === 'ENOENT' ? 404 : 400)).send({error:error.message})
  })
  const segment = value => {
    if (!value || value === '.' || value === '..' || /[/\\\0]/.test(value)) throw Error('Invalid path segment')
    return value
  }
  const rootFor = async id => runFile(join(directory,'runs'),segment(id))
  const settingsFor = async root => {
    try { return JSON.parse(await readFile(join(root,'settings.json'),'utf8')) }
    catch (error) { if(error.code==='ENOENT')return {};throw error }
  }
  const turnPath = p => `windows/${segment(p.window)}/forks/${segment(p.fork)}/turns/${segment(p.turn)}`
  app.get('/api/runs', () => readExperiment(directory))
  app.get('/api/runs/index', () => readRunIndex(directory))
  app.get('/api/runs/:run/summary',async request => {
    const warnings=new Set()
    const row=await runSummary(await rootFor(request.params.run),warnings)
    return {row,warnings:[...warnings]}
  })
  app.get('/api/runs/:run', async request => {
    const root = await rootFor(request.params.run)
    return {diagram:await readRunDiagram(root,await settingsFor(root))}
  })
  app.get('/api/runs/:run/windows/:window/forks/:fork/turns/:turn/transcript',async request => {
    const p=request.params,root=await rootFor(p.run)
    await runFile(root,turnPath(p))
    return {messages:await readTurnTranscript(root,p.window,p.fork,p.turn)}
  })
  app.get('/api/runs/:run/windows/:window/forks/:fork/turns/:turn/ts/:sample',async request => {
    const p=request.params,root=await rootFor(p.run)
    return readSample(await runFile(root,`${turnPath(p)}/ts/${segment(p.sample)}`),root)
  })
  app.get('/api/runs/:run/files/*',async (request,reply) => {
    const path=await runFile(await rootFor(request.params.run),request.params['*'])
    reply.type('text/plain; charset=utf-8').header('X-Content-Type-Options','nosniff')
    return (await stat(path)).isDirectory() ? sourceBytes(path) : reply.send(createReadStream(path))
  })
  app.get('/api/runs/:run/problem/:file',async (request,reply) => {
    const root=await rootFor(request.params.run),settings=await settingsFor(root)
    const file=(await readProblem(directory,settings.problem_dir)).find(f=>f.name===request.params.file)
    if(file?.text==null)return reply.code(404).send({error:'Problem file not recorded'})
    return reply.type('text/plain; charset=utf-8').header('X-Content-Type-Options','nosniff').send(file.text)
  })
  return app
}
