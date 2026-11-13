import {shallowRef,watch} from 'vue'
import {readState,routeHash,setUrlState,clearUrlState} from './urlState.js'
import {turnSummary} from './outcomes.js'
import {fileRoute} from './fileMatcher.js'

export const filePreview=shallowRef(null)
let currentDescriptor='',restoreSequence=0
const descriptorFile=file=>Object.fromEntries(['source','url','name','path','error','timedOut'].filter(key=>file[key]!=null).map(key=>[key,file[key]]))
function remember(preview) {
  if(typeof location==='undefined')return
  const context=preview?.uNavigation?.()
  const descriptor=preview ? Object.fromEntries(['kind','src','name','title','line','uView','testCase','measurement'].filter(key=>preview[key]!=null).map(key=>[key,preview[key]])) : null
  if(preview?.files)descriptor.files=preview.files.map(descriptorFile)
  if(context)descriptor.turn={window:context.window,fork:context.fork,id:preview.uTurnId}
  currentDescriptor=JSON.stringify(descriptor)
  restoreSequence++
  setUrlState('modal',descriptor)
}
function present(preview){filePreview.value=preview;remember(preview)}
function sourceViewer(sourceUrl,name,line) {
  const url=new URL(location.href)
  url.hash=`files/${encodeURIComponent(name)}?${new URLSearchParams({src:sourceUrl,...(line?{line:String(line)}:{})})}`
  return url.href
}
export function restoreModals() {
  return watch(()=>JSON.stringify(readState(routeHash.value,'modal',null)),async encoded=>{
    if(encoded===currentDescriptor)return
    currentDescriptor=encoded
    const sequence=++restoreSequence,descriptor=JSON.parse(encoded)
    if(!descriptor){filePreview.value=null;return}
    const preview={...descriptor}
    try{
      const file=preview.files?.[0],src=file?.url??preview.src
      const root=src?.match(/^(\/api\/runs\/[^/]+)/)?.[1]
      preview.sourceUrl=(name,line)=>sourceViewer(`${root}/files/${name}`,name,line)
      preview.rawFiles=preview.files?.slice(0,1)??[{url:preview.src,source:preview.name}]
      if(preview.kind==='transcript')preview.source=file.source
      if(preview.turn){
        const response=await fetch(root)
        if(!response.ok)throw Error(`Cannot restore turn: HTTP ${response.status}`)
        const {diagram}=await response.json(),target=preview.turn
        const fork=diagram.find(w=>w.id===target.window)?.forks.find(f=>f.id===target.fork)
        let turns=[...(fork?.parallel??[]),...(fork?.solo??[])].map(turn=>({...turn,solo:fork.solo.includes(turn)})).sort((a,b)=>a.id-b.id)
        if(preview.kind==='advice')turns=turns.filter(turn=>turn.advice!=null)
        const turn=turns.find(t=>t.id===target.id)
        if(!turn)throw Error('Turn no longer available')
        preview.uTurnId=turn.id;preview.turnMetadata=turn.metadata
        preview.uNavigation=()=>({window:target.window,fork:target.fork,turn:turn.id,turns})
        if(preview.kind==='advice')Object.assign(preview,advicePreview(preview))
      } else if(preview.src?.endsWith('/advice.txt')) {
        const response=await fetch(preview.src.replace(/advice\.txt$/,'advice.json'))
        if(response.ok)preview.tokens=(await response.json()).tokens
      }
      if(sequence===restoreSequence)filePreview.value=preview
    }catch(error){if(sequence===restoreSequence)filePreview.value={...preview,restoreError:error.message}}
  },{immediate:true})
}
export function openFile(url, options={}) {
  const route=fileRoute(new URL(url,location.href).hash)
  if(route){
    const name=route.get('name'),src=route.get('src'),filename=name.split('/').at(-1)
    const title=filename==='advice.txt'?'Advice':filename==='tests.json'?'Test results':filename
    present({src,name,title,line:route.get('line'),rawFiles:[{url:src,source:name}],...options})
  }
}
export function openTranscript(preview,file=preview.files[0]) {
  const context=preview.uNavigation?.()
  if(context){
    const id=preview.uTurnId ?? context.turn,turn=context.turns.find(turn=>turn.id===id)
    if(turn){
      const hash=turn.metadata?.u_request_sha256
      preview={...preview,uTurnId:id,turnMetadata:turn.metadata,name:`U transcript · Window ${context.window} · Fork ${context.fork} · Turn ${id}${hash ? ` · u_request_sha256: ${hash}` : ''}`}
    }
  }
  present({...preview,kind:'transcript',files:[file],source:file.source,rawFiles:[file]})
}
let adviceTransition=0
function advicePreview({sourceUrl,uNavigation,uTurnId,previousText}) {
  const navigation=()=>{const context=uNavigation();return {...context,turns:context.turns.filter(turn=>turn.advice!=null)}}
  const context=navigation(),id=uTurnId??context.turn,turn=context.turns.find(turn=>turn.id===id)
  const comparison=context.turns[context.turns.findIndex(t=>t.id===id)-1]
  const route=fileRoute(new URL(sourceUrl(turn.adviceSource),location.href).hash)
  const src=route.get('src'),name=route.get('name')
  return {kind:'advice',src,name,sourceUrl,uNavigation:navigation,uTurnId:id,previousText,highlightId:++adviceTransition,
    title:`Window ${context.window} · Fork ${context.fork}${turn.solo?' continues':''} · Turn ${id} · Advice`,
    comparisonText:comparison?.advice,comparisonTokens:comparison?.tokens,
    initialText:turn.advice,tokens:turn.tokens,measurement:turn.measurement==null?'Measurement unavailable':turnSummary(turn),
    rawFiles:[{url:src,source:name}]}
}
export function openAdvice(preview) {present(advicePreview(preview))}
export function stepUTurn(direction) {
  const preview=filePreview.value,context=preview?.uNavigation?.()
  if(!context)return
  const index=context.turns.findIndex(turn=>turn.id===preview.uTurnId)
  const turn=context.turns[index+direction]
  if(index>=0 && turn){
    const next={...preview,uTurnId:turn.id}
    if(preview.kind==='advice')openAdvice({...next,previousText:preview.initialText})
    else openTranscript(next)
  }
}
export function openFiles(preview) {present({...preview,kind:'files',rawFiles:preview.files.slice(0,1).map(file=>({url:file.url,source:file.source}))})}
export function selectPreviewFile(file) {
  if(filePreview.value?.kind==='files' && file)filePreview.value={...filePreview.value,rawFiles:[{url:file.url,source:file.source}]}
}
export function closeFile() {
  present(null)
  if(typeof location!=='undefined')clearUrlState(key=>/^(advice:|transcript:|file:|json:|scroll:(modal|blocks|files|json)$)/.test(key)||key.startsWith('panel:windows/')||key.startsWith('panel:/api/'))
}
