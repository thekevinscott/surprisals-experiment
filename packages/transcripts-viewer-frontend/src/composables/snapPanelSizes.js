export function snapPanelSizes([graph,transcripts]) {
  const share=100*graph/(graph+transcripts)
  if(share<15)return [0,100]
  if(share>85)return [100,0]
  return [share,100-share]
}
