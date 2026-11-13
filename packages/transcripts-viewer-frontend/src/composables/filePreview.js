import {shallowRef} from 'vue'
import {fileRoute} from './fileMatcher.js'

export const filePreview=shallowRef(null)
export function openFile(url, options={}) {
  const route=fileRoute(new URL(url,location.href).hash)
  if(route){
    const name=route.get('name'),src=route.get('src'),filename=name.split('/').at(-1)
    const title=filename==='advice.txt'?'Advice':filename==='tests.json'?'Test results':filename
    filePreview.value={src,name,title,line:route.get('line'),rawFiles:[{url:src,source:name}],...options}
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
  filePreview.value={...preview,kind:'transcript',files:[file],source:file.source,rawFiles:[file]}
}
export function stepUTurn(direction) {
  const preview=filePreview.value,context=preview?.uNavigation?.()
  if(!context)return
  const index=context.turns.findIndex(turn=>turn.id===preview.uTurnId)
  const turn=context.turns[index+direction]
  if(index>=0 && turn)openTranscript({...preview,uTurnId:turn.id})
}
export function openFiles(preview) {filePreview.value={...preview,kind:'files',rawFiles:preview.files.slice(0,1).map(file=>({url:file.url,source:file.source}))}}
export function selectPreviewFile(file) {
  if(filePreview.value?.kind==='files' && file)filePreview.value={...filePreview.value,rawFiles:[{url:file.url,source:file.source}]}
}
export function closeFile() {filePreview.value=null}
