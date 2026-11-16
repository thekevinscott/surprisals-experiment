export const queryTimeout=url=>Object.assign(Error(`Query exceeded 500 ms: ${url}`),{name:'QueryTimeoutError'})

// Include response-body reading in the deadline, not just response headers.
export async function request(url,options={},read=response=>response){
  const controller=new AbortController()
  const signal=options.signal?AbortSignal.any([options.signal,controller.signal]):controller.signal
  let timer
  const start=performance.now()
  try{
    const result=await Promise.race([
      (async()=>{
        const response=await fetch(url,{...options,signal})
        return read(response)
      })(),
      new Promise((_,reject)=>{timer=setTimeout(()=>{const error=queryTimeout(url);reject(error);controller.abort(error)},500)}),
    ])
    if(performance.now()-start>=500)throw queryTimeout(url)
    return result
  }finally{clearTimeout(timer)}
}
export async function readResponse(response,format){
  if(!response.ok)throw Error(`HTTP ${response.status}: ${await response.text()}`)
  return response[format]()
}
