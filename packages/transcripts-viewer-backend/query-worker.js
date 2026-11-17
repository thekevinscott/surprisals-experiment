import {parentPort,workerData} from 'node:worker_threads'
import {createApi} from './server.js'

const api=createApi(workerData.directory)
await api.ready()
parentPort.postMessage({ready:true})
parentPort.on('message',async({id,url,close})=>{
  if(close){await api.close();parentPort.close();return}
  try{
    const response=await api.inject({method:'GET',url})
    parentPort.postMessage({id,response:{status:response.statusCode,type:response.headers['content-type'],body:response.rawPayload}})
  }catch(error){parentPort.postMessage({id,error:error.message})}
})
