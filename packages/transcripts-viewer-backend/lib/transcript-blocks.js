import {open} from 'node:fs/promises'
import {join} from 'node:path'

export function createTranscriptReader(db) {
  return {
    async metadata(path,count=null){
      const [{payload}]=await db.query(`WITH lines AS (SELECT line AS position,type FROM transcript_lines WHERE run=:run AND path=:path),
      reply AS (SELECT EXISTS(SELECT 1 FROM lines WHERE position=:count AND type='assistant') AS present),
      result AS (SELECT json_object('total',(SELECT count(*) FROM lines),'blocks',json_group_array(json_object('index',position,'type',type))) AS payload FROM (SELECT position,type FROM lines WHERE :count IS NULL OR position<:count+(SELECT present FROM reply) ORDER BY position))
      SELECT CASE WHEN :count IS NULL THEN payload ELSE json_set(payload,'$.hasReply',json(CASE WHEN present THEN 'true' ELSE 'false' END)) END AS payload FROM result CROSS JOIN reply`,{run:path.split('/')[1],path,count})
      return JSON.parse(payload)
    },
    async blocks(path,start,end){
      const rows=await db.query('SELECT line,offset,length FROM transcript_lines WHERE run=? AND path=? AND line>=? AND line<? ORDER BY line',[path.split('/')[1],path,start,end])
      const file=await open(join(db.root,path),'r')
      try{
        const blocks=[]
        for(const row of rows){
          const buffer=Buffer.alloc(row.length)
          const {bytesRead}=await file.read(buffer,0,row.length,row.offset)
          blocks.push({index:row.line,raw:buffer.subarray(0,bytesRead).toString('utf8')})
        }
        return {blocks}
      }finally{await file.close()}
    },
  }
}
