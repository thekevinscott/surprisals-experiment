export async function request(url,options={},read=response=>response){
  return read(await fetch(url,options))
}
export async function readResponse(response,format){
  if(!response.ok)throw Error(`HTTP ${response.status}: ${await response.text()}`)
  return response[format]()
}
