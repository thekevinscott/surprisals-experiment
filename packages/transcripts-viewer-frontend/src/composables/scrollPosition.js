import {computed,toValue,watch} from 'vue'
import {useScroll,useResizeObserver,useMutationObserver,useWindowScroll,watchDebounced} from '@vueuse/core'
import {useJsonQuery} from './queryState.js'
import {pageRestoring} from './pageScroll.js'

export function usePageScroll() {
  const position=useJsonQuery('scroll:page',[0,0]),{x,y}=useWindowScroll()
  watchDebounced([x,y],()=>{
    if(!pageRestoring.value)position.value=[Math.round(x.value),Math.round(y.value)]
  },{debounce:150})
}
export function useContainerScroll(key,element,identity=()=>null) {
  const position=useJsonQuery(`scroll:${key}`,[0,0])
  let pending
  function restore() {
    const target=toValue(element)
    if(!target||!pending)return
    target.scrollTo(...pending)
    if(Math.abs(target.scrollLeft-pending[0])<2&&Math.abs(target.scrollTop-pending[1])<2)pending=null
  }
  watch([position,element,identity],()=>{pending=position.value;restore()},{immediate:true,flush:'post'})
  useScroll(element,{onStop:()=>{
    const target=toValue(element)
    if(target&&!pending)position.value=[Math.round(target.scrollLeft),Math.round(target.scrollTop)]
  }})
  // Overflow containers are outside router scrollBehavior. Retry a saved offset
  // as asynchronous file/turn contents grow enough to reach it.
  useResizeObserver([element,computed(()=>toValue(element)?.firstElementChild)],restore)
  useMutationObserver(element,restore,{childList:true,subtree:true})
}
