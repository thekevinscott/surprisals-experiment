import {parentPort,workerData} from 'node:worker_threads'
import {createApi} from './server.js'

const api=createApi(workerData.directory)
parentPort.on('message',async({id,url,expires})=>{
  if(Date.now()>=expires){
    parentPort.postMessage({id,response:{status:504,type:'application/json',body:JSON.stringify({error:`Query exceeded 500 ms: ${url}`})}})
    return
  }
  try{
    const response=await api.inject({method:'GET',url})
    parentPort.postMessage({id,response:{status:response.statusCode,type:response.headers['content-type'],body:response.rawPayload}})
  }catch(error){parentPort.postMessage({id,error:error.message})}
})
