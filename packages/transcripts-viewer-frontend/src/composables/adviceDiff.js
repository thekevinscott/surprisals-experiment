import {diffWordsWithSpace} from 'diff'

export function addedRanges(previous,text) {
  let offset=0
  return diffWordsWithSpace(previous,text).flatMap(part=>{
    if(part.removed)return []
    const start=offset;offset+=part.value.length
    return part.added ? [[start,offset]] : []
  })
}
export function highlightParts(text,ranges,offset=0) {
  const ends=new Set([0,text.length])
  for(const [start,end] of ranges)for(const edge of [start-offset,end-offset])if(edge>0&&edge<text.length)ends.add(edge)
  const edges=[...ends].sort((a,b)=>a-b)
  return edges.slice(0,-1).map((start,i)=>({text:text.slice(start,edges[i+1]),added:ranges.some(([a,b])=>start+offset>=a&&start+offset<b)}))
}
