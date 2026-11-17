import {quote} from './experiment-database.js'

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
      const [{payload}]=await db.query(`WITH source AS MATERIALIZED (
        SELECT CAST(content AS BLOB) AS bytes FROM ${quote('./'+path)}
      ), blocks AS (
        SELECT line AS position,CAST(substr(bytes,offset+1,length) AS TEXT) AS raw
        FROM transcript_lines CROSS JOIN source
        WHERE run=:run AND path=:path AND line>=:start AND line<:end ORDER BY line
      ) SELECT json_object('blocks',json_group_array(json_object('index',position,'raw',raw))) AS payload FROM blocks`,
      {run:path.split('/')[1],path,start,end})
      return JSON.parse(payload)
    },
  }
}
