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
export function openTranscript(preview) {filePreview.value={...preview,kind:'transcript'}}
export function openFiles(preview) {filePreview.value={...preview,kind:'files',rawFiles:preview.files.slice(0,1).map(file=>({url:file.url,source:file.source}))}}
export function selectPreviewFile(file) {
  if(filePreview.value?.kind==='files' && file)filePreview.value={...filePreview.value,rawFiles:[{url:file.url,source:file.source}]}
}
export function closeFile() {filePreview.value=null}
