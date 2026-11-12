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
  function visible(index, isVisible) {
    if(!isVisible){active.get(index)?.();active.delete(index);return}
    if(active.has(index))return
    const message=messages[index]
    active.set(index,subscribe(message.blocksUrl,data=>{
      const block=data.blocks.find(block=>block.index===message.index)
      if(block)message.raw=block.raw
    }))
  }
  return {visible,dispose(){for(const stop of active.values())stop();active.clear()}}
}
