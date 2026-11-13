import {computed,ref,toValue} from 'vue'

export const routeHash=ref(typeof location==='undefined' ? '' : location.hash)
if(typeof window!=='undefined')window.addEventListener('hashchange',()=>{routeHash.value=location.hash})
export function readState(hash,key,fallback) {
  const raw=new URLSearchParams(hash.split('?')[1]).get(key)
  if(raw===null)return fallback
  try{return JSON.parse(raw)}catch{return fallback}
}
export function stateHash(hash,key,value,fallback) {
  const [path,query]=hash.split('?'),params=new URLSearchParams(query)
  if(JSON.stringify(value)===JSON.stringify(fallback))params.delete(key)
  else params.set(key,JSON.stringify(value))
  return (path||'#dashboard')+(params.size?`?${params}`:'')
}
export function setUrlState(key,value,fallback=null) {
  const hash=stateHash(location.hash,key,value,fallback)
  if(hash!==location.hash)history.replaceState(null,'',hash)
  routeHash.value=hash
}
export function useUrlState(key,fallback) {
  return computed({
    get:()=>readState(routeHash.value,toValue(key),toValue(fallback)),
    set:value=>setUrlState(toValue(key),value,toValue(fallback)),
  })
}

export function clearUrlState(matches) {
  const [path,query]=location.hash.split('?'),params=new URLSearchParams(query)
  for(const key of [...params.keys()])if(matches(key))params.delete(key)
  const hash=path+(params.size?`?${params}`:'')
  history.replaceState(null,'',hash);routeHash.value=hash
}
