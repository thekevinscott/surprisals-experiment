#!/usr/bin/env node
import {parseArgs} from 'node:util'
import {dirname,resolve} from 'node:path'
import {fileURLToPath} from 'node:url'
import {stat} from 'node:fs/promises'
import {createServer} from 'vite'
import {createApi} from '../../transcripts-viewer-backend/server.js'

let api,vite
try {
  const {values,positionals}=parseArgs({allowPositionals:true,options:{port:{type:'string',default:'5173'},help:{type:'boolean',short:'h'}}})
  if(values.help){
    console.log('Usage: transcripts-viewer [directory] [--port 5173]\n\nServes a Vue frontend and live REST API from directory/runs.\nDirectory defaults to the current working directory.')
  }else{
    if(positionals.length>1)throw Error('Expected one experiment directory')
    const port=Number(values.port)
    if(!Number.isInteger(port)||port<1||port>65535)throw Error('Port must be between 1 and 65535')
    const directory=resolve(positionals[0]??process.cwd())
    if(!(await stat(resolve(directory,'runs'))).isDirectory())throw Error('Expected a runs directory')
    const root=resolve(dirname(fileURLToPath(import.meta.url)),'..')
    api=createApi(directory)
    vite=await createServer({root,configFile:resolve(root,'vite.config.js'),server:{middlewareMode:true,ws:{server:api.server}}})
    api.setNotFoundHandler((request,reply)=>{
      if(request.url.startsWith('/api/'))return reply.code(404).send({error:'Endpoint not found'})
      reply.hijack()
      vite.middlewares(request.raw,reply.raw,()=>{reply.raw.statusCode=404;reply.raw.end('Not found')})
    })
    await api.listen({port,host:'0.0.0.0'})
    console.log(`Experiment: ${directory}\nViewer: http://duncan.tail790bbc.ts.net:${port}/`)
    for(const signal of ['SIGINT','SIGTERM'])process.once(signal,async()=>{await vite.close();await api.close();process.exit(0)})
  }
}catch(error){
  await vite?.close();await api?.close()
  console.error(`transcripts-viewer: ${error.message}`)
  process.exit(1)
}
