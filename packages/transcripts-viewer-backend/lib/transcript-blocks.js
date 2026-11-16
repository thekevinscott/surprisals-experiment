import {DirSQL} from 'dirsql'
import {readFileSync} from 'node:fs'
import {open} from 'node:fs/promises'
import {dirname,resolve} from 'node:path'

export function createTranscriptReader() {
  const indexes=new Map()
  function index(path) {
    path=resolve(path)
    if(!indexes.has(path)){
      const db=new DirSQL({root:dirname(path),noIgnore:true,tables:[{
        name:'lines',ddl:'CREATE TABLE lines (position INTEGER PRIMARY KEY, offset INTEGER, length INTEGER, type TEXT)',glob:'*',
        onFile:source=>{
          if(resolve(source)!==path)return []
          const bytes=readFileSync(source),rows=[]
          let start=0
          while(start<bytes.length){
            const newline=bytes.indexOf(10,start),end=newline<0?bytes.length:newline
            let type=''
            try{const record=JSON.parse(bytes.subarray(start,end).toString('utf8'));type=record?.message?.role??record?.role??record?.type??''}catch{}
            rows.push({position:rows.length,offset:start,length:end-start,type})
            start=end+1
          }
          return rows
        },
      }]})
      indexes.set(path,db)
    }
    return indexes.get(path)
  }
  return {
    async metadata(path){
      const [{payload}]=await index(path).query(`SELECT json_object('total',count(*),'blocks',json_group_array(json_object('index',position,'type',type))) AS payload FROM (SELECT position,type FROM lines ORDER BY position)`)
      return JSON.parse(payload)
    },
    async blocks(path,start,end){
      const rows=await index(path).query('SELECT position,offset,length FROM lines WHERE position>=? AND position<? ORDER BY position',[start,end])
      const file=await open(path,'r')
      try{
        const blocks=[]
        for(const row of rows){
          const buffer=Buffer.alloc(row.length)
          const {bytesRead}=await file.read(buffer,0,row.length,row.offset)
          blocks.push({index:row.position,raw:buffer.subarray(0,bytesRead).toString('utf8')})
        }
        return {blocks}
      }finally{await file.close()}
    },
    async close(){for(const db of indexes.values()){await db.ready;db.close()}indexes.clear()},
  }
}
