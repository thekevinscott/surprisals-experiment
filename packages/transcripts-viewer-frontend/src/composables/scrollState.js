import {watch} from 'vue'
import {routeHash,readState,setUrlState} from './urlState.js'

// Restore after async panels/files have enough content to reach the saved offset.
export function installScrollState() {
  const selectors={page:()=>document.scrollingElement,modal:()=>document.querySelector('.p-dialog-content'),
    transcripts:()=>document.querySelector('.run-transcripts > .p-panel-content-container'),
    graphs:()=>document.querySelector('.run-graphs > .p-panel-content-container'),
    blocks:()=>document.querySelector('.p-dialog .block-navigation'),files:()=>document.querySelector('.files-viewer nav'),
    json:()=>document.querySelector('.p-dialog .json-content')}
  let pending=new Map(),frame,timer
  const restore=()=>{
    cancelAnimationFrame(frame)
    frame=requestAnimationFrame(()=>{
      for(const [key,[left,top]] of pending){
        const element=selectors[key]()
        if(!element)continue
        element.scrollTo(left,top)
        if(Math.abs(element.scrollLeft-left)<2&&Math.abs(element.scrollTop-top)<2)pending.delete(key)
      }
    })
  }
  const stop=watch(()=>[routeHash.value.split('?')[0],JSON.stringify(readState(routeHash.value,'modal',null))].join('|'),()=>{
    clearTimeout(timer)
    pending=new Map(Object.keys(selectors).map(key=>[key,readState(routeHash.value,`scroll:${key}`,null)]).filter(([,value])=>value))
    restore()
  },{immediate:true})
  const observer=new MutationObserver(restore)
  observer.observe(document.body,{childList:true,subtree:true})
  const resized=new ResizeObserver(restore);resized.observe(document.body)
  function scroll(event) {
    const target=event.target===document?document.scrollingElement:event.target
    const key=Object.keys(selectors).find(key=>selectors[key]()===target)
    if(!key||pending.has(key))return
    clearTimeout(timer)
    timer=setTimeout(()=>setUrlState(`scroll:${key}`,[Math.round(target.scrollLeft),Math.round(target.scrollTop)],[0,0]),150)
  }
  document.addEventListener('scroll',scroll,true)
  return ()=>{stop();observer.disconnect();resized.disconnect();cancelAnimationFrame(frame);clearTimeout(timer);document.removeEventListener('scroll',scroll,true)}
}
