export function sampleFiles(attempts, rawUrl) {
  return attempts.flatMap(attempt=>attempt.files.map(file=>({
    ...file,url:rawUrl(file.source),path:attempts.length>1?`Attempt ${attempt.id}/${file.name}`:file.name,
  })))
}

export function fileTree(files) {
  const roots=[]
  for(const file of files){
    const parts=file.path.split('/')
    let children=roots
    for(const name of parts.slice(0,-1)){
      let folder=children.find(node=>node.name===name && node.children)
      if(!folder){folder={name,children:[]};children.push(folder)}
      children=folder.children
    }
    children.push({name:parts.at(-1),file})
  }
  return roots
}
