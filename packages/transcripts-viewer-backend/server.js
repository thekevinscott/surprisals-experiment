// import {costSnapshot} from './lib/costs.js'
import Fastify from 'fastify'
import {createReadStream} from 'node:fs'
import {realpath,stat} from 'node:fs/promises'
import {join,relative,resolve} from 'node:path'
import {readExperiment,readRunIndex,runSettings,runSummary,readRunDiagram,readSample} from './lib/experiment.js'
import {ExperimentDatabase} from './lib/experiment-database.js'
import {createEvents} from './lib/events.js'
import {readProblem} from './lib/problem.js'
import {runFile,sourceBytes} from './lib/run-files.js'
import {createTranscriptReader} from './lib/transcript-blocks.js'

export function createApi(directory) {
  directory=resolve(directory)
  const app=Fastify(), db=new ExperimentDatabase(directory), events=createEvents(), readTranscript=createTranscriptReader(db)
  app.addHook('onRequest',async(_request,reply)=>{reply.header('Cache-Control','no-store')})
  app.addHook('preClose',async()=>{await events.close()})
  app.addHook('onClose',async()=>{await db.close()})
  app.setErrorHandler((error,_request,reply)=>reply.code(error.statusCode??(error.code==='ENOENT'?404:400)).send({error:error.message}))
  const segment=value=>{
    if(!value||value==='.'||value==='..'||/[/\\\0]/.test(value))throw Error('Invalid path segment')
    return value
  }
  const rootFor=async id=>runFile(join(directory,'runs'),segment(id))
  const turnPath=p=>`windows/${segment(p.window)}/forks/${segment(p.fork)}/turns/${segment(p.turn)}`
  const wantsEvents=request=>request.headers.accept?.split(',').some(type=>type.trim().startsWith('text/event-stream'))
  const endpoint=(path,load)=>app.get(path,async(request,reply)=>{
    if(wantsEvents(request))return events.stream(request,reply,()=>load(request))
    return load(request)
  })
  const streamResources=(reply,urls)=>{
    if(!Array.isArray(urls)||urls.some(url=>typeof url!=='string'||!/^\/api\/runs(?:\/|$)/.test(url)||/[?#\r\n]/.test(url)))throw Error('Expected an array of API resource paths')
    return events.multiplex(reply,[...new Set(urls)],async url=>{
      const response=await app.inject({method:'GET',url})
      if(response.statusCode>=400)throw Object.assign(Error(response.json().error),{statusCode:response.statusCode})
      return response.headers['content-type']?.startsWith('application/json') ? response.json() : response.body
    })
  }
  app.get('/api/events',async(request,reply)=>streamResources(reply,JSON.parse(request.query.resources ?? '[]')))
  app.post('/api/events',async(request,reply)=>streamResources(reply,request.body?.resources))
  // endpoint('/api/runs/costs',()=>costSnapshot(db))
  // endpoint('/api/runs/runpod-costs',()=>db.query('SELECT id,gpu,costPerHr,start,stop FROM pod_records ORDER BY path'))
  endpoint('/api/runs',()=>readExperiment(db))
  endpoint('/api/runs/index',()=>readRunIndex(db))
  endpoint('/api/runs/:run/details',async request=>{
    await rootFor(request.params.run)
    return {row:await runSummary(db,request.params.run),warnings:[]}
  })
  endpoint('/api/runs/:run/summary',async request=>{
    const warnings=new Set()
    await rootFor(request.params.run)
    return {row:await runSummary(db,request.params.run,warnings),warnings:[...warnings]}
  })
  endpoint('/api/runs/:run',async request=>{
    await rootFor(request.params.run)
    return {diagram:await readRunDiagram(db,request.params.run)}
  })
  endpoint('/api/runs/:run/windows/:window/forks/:fork/turns/:turn/ts/:sample',async request=>{
    const p=request.params,root=await rootFor(p.run)
    await runFile(root,`${turnPath(p)}/ts/${segment(p.sample)}`)
    return readSample(db,p.run,p)
  })
  const transcriptFor=async request=>relative(await realpath(directory),await runFile(await rootFor(request.params.run),request.params['*']))
  endpoint('/api/runs/:run/transcripts/*',async request=>readTranscript.metadata(await transcriptFor(request)))
  endpoint('/api/runs/:run/transcript-context/:count/*',async request=>{
    const count=Number(request.params.count)
    if(!Number.isSafeInteger(count)||count<0)throw Error('Invalid transcript context length')
    return readTranscript.metadata(await transcriptFor(request),count)
  })
  endpoint('/api/runs/:run/transcript-blocks/:start/:end/*',async request=>{
    const start=Number(request.params.start),end=Number(request.params.end)
    if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<0||end<start)throw Error('Invalid block range')
    return readTranscript.blocks(await transcriptFor(request),start,end)
  })
  app.get('/api/runs/:run/files/*',async(request,reply)=>{
    const pathFor=async()=>runFile(await rootFor(request.params.run),request.params['*'])
    if(wantsEvents(request))return events.stream(request,reply,async()=>String(await sourceBytes(await pathFor())))
    const path=await pathFor()
    reply.type('text/plain; charset=utf-8').header('X-Content-Type-Options','nosniff')
    return (await stat(path)).isDirectory()?sourceBytes(path):reply.send(createReadStream(path))
  })
  app.get('/api/runs/:run/problem/:file',async(request,reply)=>{
    const load=async()=>{
      await rootFor(request.params.run)
      const settings=await runSettings(db,request.params.run)
      const file=(await readProblem(db,directory,settings.problem_dir)).find(f=>f.name===request.params.file)
      if(file?.text==null)throw Object.assign(Error('Problem file not recorded'),{statusCode:404})
      return file.text
    }
    if(wantsEvents(request))return events.stream(request,reply,load)
    reply.type('text/plain; charset=utf-8').header('X-Content-Type-Options','nosniff')
    return load()
  })
  return app
}
