import {DirSQL} from 'dirsql'
import {readFileSync} from 'node:fs'
import {relative,join,basename} from 'node:path'

const schema=readFileSync(new URL('./costs.sql',import.meta.url),'utf8')
export class CostDatabase {
  constructor(root,{experiment=false}={}) {
    const prefix=experiment?'runs/*/':''
    const run=path=>experiment?relative(root,path).split('/')[1]:basename(root)
    const usage=path=>{
      const kind=relative(root,path).includes('/u/')?'u':'t'
      return readFileSync(path,'utf8').split('\n').flatMap((line,index)=>{
        if(!line.trim())return []
        const base={run:run(path),kind,path:relative(root,path),line:index,completion_id:null,cost:null,incomplete:0,billable:0}
        let record
        try{record=JSON.parse(line)}catch{return [{...base,incomplete:1}]}
        const value=kind==='u' ? record.usage??(record.role==='assistant'?{}:null) : record.type==='message'?record.message?.usage:null
        const cost=typeof value?.cost==='object'?value.cost?.total:value?.cost
        return [{...base,completion_id:record.completion_id?String(record.completion_id):null,cost:typeof cost==='number'?cost:null,billable:value?1:0}]
      })
    }
    const sources={
      cost_runs:[`${prefix}run.json`,path=>{
        const meta=readFileSync(path,'utf8')
        try{JSON.parse(meta)}catch(error){throw Error(`Cannot read ${path}: ${error.message}`)}
        return [{id:run(path),meta}]
      }],
      usage_records:[`${prefix}windows/*/forks/*/{u/transcript.jsonl,turns/*/ts/*/attempts/*/transcripts/*/*.jsonl}`,usage],
      launches:[`${prefix}stderr-*.txt`,path=>{
        for(const line of readFileSync(path,'utf8').split('\n')){
          const match=line.match(/^(\S+) instance launched\s*$/)
          if(match&&Number.isFinite(Date.parse(match[1])))return [{run:run(path),path:relative(root,path),launched:new Date(match[1]).toISOString()}]
        }
        return []
      }],
      pods:[experiment?'runpod-costs/*.json':'',path=>{
        const {id,gpu,costPerHr,start,stop}=JSON.parse(readFileSync(path,'utf8'))
        return [{id,gpu,costPerHr,start,stop}]
      }],
    }
    this.db=new DirSQL({root,noIgnore:true,tables:schema.split(';').filter(s=>s.trim()).map(ddl=>{
      const name=ddl.match(/CREATE (?:TABLE|VIEW) (\w+)/)[1], [glob,onFile]=sources[name]??['',()=>[]]
      return {name,ddl,glob,onFile}
    })})
    this.pending=Promise.resolve()
  }
  query(sql,params){
    const result=this.pending.then(()=>this.db.query(sql,params))
    this.pending=result.then(()=>undefined,()=>undefined)
    return result
  }
  async snapshot(now=Date.now()) {
    const [{payload}]=await this.query(`WITH priced AS (
      SELECT *,max(0,(coalesce(unixepoch(ended,'subsec'),:now/1000.0)-unixepoch(awsLaunched,'subsec')))/3600*0.1008 AS awsCost FROM cost_rows
    ), totals AS (
      SELECT coalesce(sum(uCost),0) AS u,coalesce(sum(tCost),0) AS t,coalesce(sum(awsCost),0) AS aws,
      count(*)-count(uCost) AS missing_u,count(*)-count(tCost) AS missing_t,count(*)-count(awsCost) AS missing_aws FROM priced
    ), pod_total AS (
      SELECT coalesce(sum(max(0,coalesce(unixepoch(stop,'subsec'),:now/1000.0)-unixepoch(start,'subsec'))/3600*costPerHr),0) AS runpod FROM pods
    ) SELECT json_object('asOf',:now,
      'rows',json((SELECT json_group_array(json_object('id',id,'uCost',uCost,'tCost',tCost,'modelCost',uCost+tCost,'awsLaunched',awsLaunched,'ended',ended,'awsCost',awsCost)) FROM (SELECT * FROM priced ORDER BY id))),
      'pods',json((SELECT json_group_array(json_object('id',id,'gpu',gpu,'costPerHr',costPerHr,'start',start,'stop',stop)) FROM pods)),
      'breakdown',json_object('u',u,'t',t,'aws',aws,'runpod',runpod,'total',u+t+aws+runpod,'missing',json_object('u',missing_u,'t',missing_t,'aws',missing_aws)),
      'warnings',json(CASE WHEN EXISTS(SELECT 1 FROM usage_records WHERE incomplete) THEN '["Incomplete usage records were skipped; costs may be partial."]' ELSE '[]' END)
    ) AS payload FROM totals CROSS JOIN pod_total`,{now})
    return JSON.parse(payload)
  }
  async close(){await this.pending;await this.db.ready;this.db.close()}
}
