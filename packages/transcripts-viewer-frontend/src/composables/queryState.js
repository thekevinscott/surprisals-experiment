import {computed,effectScope,getCurrentScope,onScopeDispose,reactive,shallowRef,toValue,watch} from 'vue'
import {useRouteQuery} from '@vueuse/router'
import {router} from '../router.js'

// VueUse owns query updates/batching. This adapter only serializes structured UI values
// and rebinds when a component's source/key changes.
export const currentRoute=reactive({
  get query(){return router.currentRoute.value.query},
  get params(){return router.currentRoute.value.params},
  get hash(){return router.currentRoute.value.hash},
})
export function useJsonQuery(key,fallback=null) {
  const query=shallowRef()
  let scope
  const stop=watch(()=>toValue(key),name=>{
    scope?.stop();scope=effectScope()
    query.value=scope.run(()=>useRouteQuery(name,undefined,{router,route:currentRoute,mode:'replace',transform:{
      get:value=>{try{return value==null?toValue(fallback):JSON.parse(value)}catch{return toValue(fallback)}},
      set:value=>JSON.stringify(value)===JSON.stringify(toValue(fallback))?undefined:JSON.stringify(value),
    }}))
  },{immediate:true,flush:'sync'})
  if(getCurrentScope())onScopeDispose(()=>{stop();scope.stop()})
  return computed({get:()=>query.value.value,set:value=>{query.value.value=value}})
}
export function clearQueries(matches) {
  const scope=effectScope()
  scope.run(()=>{
    for(const key of Object.keys(currentRoute.query))if(matches(key))useRouteQuery(key,undefined,{router,route:currentRoute,mode:'replace'}).value=undefined
  })
  scope.stop()
}
