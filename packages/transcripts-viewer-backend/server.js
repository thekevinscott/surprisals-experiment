import Fastify from 'fastify'
import {createReadStream} from 'node:fs'
import {stat} from 'node:fs/promises'
import {join,resolve} from 'node:path'
import {readExperiment,readRunIndex,runSummary,readRunDiagram,readTurnTranscript,readSample} from './lib/experiment.js'
import {ExperimentDatabase} from './lib/experiment-database.js'
import {createEvents} from './lib/events.js'
import {readProblem} from './lib/problem.js'
import {runFile,sourceBytes} from './lib/run-files.js'
import {createTranscriptReader} from './lib/transcript-blocks.js'

export function createApi(directory) {
  directory=resolve(directory)
  const app=Fastify(), databases=new Map(), events=createEvents(), readTranscript=createTranscriptReader()
  const database=(root,relations=true)=>{
    const key=`${root}:${relations}`
    if(!databases.has(key))databases.set(key,new ExperimentDatabase(root,{relations}))
    return databases.get(key)
  }
  app.addHook('onRequest',async(_request,reply)=>{reply.header('Cache-Control','no-store')})
  app.addHook('preClose',async()=>{await events.close()})
  app.addHook('onClose',async()=>{for(const db of databases.values())await db.close()})
  app.setErrorHandler((error,_request,reply)=>reply.code(error.statusCode??(error.code==='ENOENT'?404:400)).send({error:error.message}))
  const segment=value=>{
    if(!value||value==='.'||value==='..'||/[/\\\0]/.test(value))throw Error('Invalid path segment')
    return value
  }
  const rootFor=async id=>runFile(join(directory,'runs'),segment(id))
  const settingsFor=root=>database(root,false).json(join(root,'settings.json'),true).then(value=>value??{})
  const turnPath=p=>`windows/${segment(p.window)}/forks/${segment(p.fork)}/turns/${segment(p.turn)}`
  const wantsEvents=request=>request.headers.accept?.split(',').some(type=>type.trim().startsWith('text/event-stream'))
  const endpoint=(path,load)=>app.get(path,async(request,reply)=>{
    if(wantsEvents(request))return events.stream(request,reply,()=>load(request))
    return load(request)
  })
  app.get('/api/events',async(request,reply)=>{
    const urls=JSON.parse(request.query.resources ?? '[]')
    if(!Array.isArray(urls)||urls.length>256||urls.some(url=>typeof url!=='string'||!/^\/api\/runs(?:\/|$)/.test(url)||/[?#\r\n]/.test(url)))throw Error('Expected an array of API resource paths')
    return events.multiplex(reply,[...new Set(urls)],async url=>{
      const response=await app.inject({method:'GET',url})
      if(response.statusCode>=400)throw Object.assign(Error(response.json().error),{statusCode:response.statusCode})
      return response.headers['content-type']?.startsWith('application/json') ? response.json() : response.body
    })
  })
  endpoint('/api/runs',()=>readExperiment(directory,root=>database(root)))
  endpoint('/api/runs/index',()=>readRunIndex(directory,database(join(directory,'runs'),false)))
  endpoint('/api/runs/:run/details',async request=>{
    const warnings=new Set(),root=await rootFor(request.params.run)
    return {row:await runSummary(root,warnings,database(root),{includeCosts:false}),warnings:[...warnings]}
  })
  endpoint('/api/runs/:run/summary',async request=>{
    const warnings=new Set(),root=await rootFor(request.params.run)
    return {row:await runSummary(root,warnings,database(root)),warnings:[...warnings]}
  })
  endpoint('/api/runs/:run',async request=>{
    const root=await rootFor(request.params.run)
    return {diagram:await readRunDiagram(root,await settingsFor(root),database(root))}
  })
  endpoint('/api/runs/:run/windows/:window/forks/:fork/turns/:turn/transcript',async request=>{
    const p=request.params,root=await rootFor(p.run)
    await runFile(root,turnPath(p))
    return {messages:await readTurnTranscript(root,p.window,p.fork,p.turn,database(root,false))}
  })
  endpoint('/api/runs/:run/windows/:window/forks/:fork/turns/:turn/ts/:sample',async request=>{
    const p=request.params,root=await rootFor(p.run)
    return readSample(await runFile(root,`${turnPath(p)}/ts/${segment(p.sample)}`),root,database(root,false))
  })
  const transcriptFor=async request=>readTranscript(await runFile(await rootFor(request.params.run),request.params['*']))
  endpoint('/api/runs/:run/transcripts/*',async request=>(await transcriptFor(request)).metadata)
  endpoint('/api/runs/:run/transcript-blocks/:start/:end/*',async request=>{
    const start=Number(request.params.start),end=Number(request.params.end)
    if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<0||end<start)throw Error('Invalid block range')
    const {lines}=await transcriptFor(request)
    return {blocks:lines.slice(start,end).map((raw,offset)=>({index:start+offset,raw}))}
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
      const root=await rootFor(request.params.run),settings=await settingsFor(root)
      const file=(await readProblem(directory,settings.problem_dir)).find(f=>f.name===request.params.file)
      if(file?.text==null)throw Object.assign(Error('Problem file not recorded'),{statusCode:404})
      return file.text
    }
    if(wantsEvents(request))return events.stream(request,reply,load)
    reply.type('text/plain; charset=utf-8').header('X-Content-Type-Options','nosniff')
    return load()
  })
  return app
}
