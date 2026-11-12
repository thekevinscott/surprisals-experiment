import {shallowRef} from 'vue'
import {fileRoute} from './fileMatcher.js'

export const filePreview=shallowRef(null)
export function openFile(url, options={}) {
  const route=fileRoute(new URL(url,location.href).hash)
  if(route)filePreview.value={src:route.get('src'),name:route.get('name'),line:route.get('line'),...options}
}
export function openTranscript(preview) {filePreview.value={...preview,kind:'transcript'}}
export function openFiles(preview) {filePreview.value={...preview,kind:'files',rawFiles:preview.files.map(file=>({url:file.url,source:file.source}))}}
export function closeFile() {filePreview.value=null}
