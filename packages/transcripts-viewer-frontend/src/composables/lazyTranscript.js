export const transcriptMetadataUrl = url => url.replace('/files/', '/transcripts/')

export function transcriptBlocks(metadata, source, url, previous=[]) {
  const loaded=new Map(previous.map(message=>[message.blocksUrl,message]))
  return metadata.blocks.map(({index,type})=>{
    const blocksUrl=url.replace('/files/', `/transcript-blocks/${index}/${index+1}/`)
    return {index,role:type,line:index+1,source,blocksUrl,raw:loaded.get(blocksUrl)?.raw}
  })
}

// Subscribe only while a block is visible. Retain its exact raw text when it
// leaves the viewport, and refresh it on reentry (including live partial records).
export function observeTranscriptBlocks(messages, subscribe) {
  const active=new Map()
  let disposed=false
  function visible(index, isVisible) {
    if(disposed)return
    if(!isVisible){active.get(index)?.();active.delete(index);return}
    if(active.has(index))return
    active.set(index,subscribe(messages[index].blocksUrl,data=>{
      if(disposed)return
      const message=messages[index]
      const block=data.blocks.find(block=>block.index===message.index)
      if(block)message.raw=block.raw
    }))
  }
  return {visible,dispose(){
    disposed=true
    for(const stop of active.values())stop()
    active.clear()
    for(const message of messages)delete message.raw
    messages=[]
  }}
}
