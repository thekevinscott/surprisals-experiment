import {DirSQL} from 'dirsql'
import {readFileSync,statSync} from 'node:fs'
import {basename, relative, resolve} from 'node:path'

const schema = readFileSync(new URL('./schema.sql', import.meta.url), 'utf8')
const quote = value => `'${value.replaceAll("'", "''")}'`

export class ExperimentDatabase {
  constructor(root) {
    this.root = resolve(root)
    // A malformed file is recorded, not thrown: a DirSQL onFile error fails every query on the instance.
    const parsed=path=>{
      const body=readFileSync(path,'utf8')
      try{JSON.parse(body);return {body,error:null}}catch(error){return {body:null,error:`Cannot read ${path}: ${error.message}`}}
    }
    const located=path=>{const rel=relative(this.root,path),parts=rel.split('/');return {rel,run:parts[1],parts:parts.slice(2)}}
    const sources = {
      pod_records:['runpod-costs/*.json',path=>{
        const {id,gpu,costPerHr,start,stop}=JSON.parse(readFileSync(path,'utf8'))
        return [{path:relative(this.root,path),id,gpu,costPerHr,start,stop}]
      }],
      stderr_files:['runs/*/stderr-*.txt',path=>{
        const {rel,run}=located(path)
        let launched=null
        for(const line of readFileSync(path,'utf8').split('\n')){
          const match=line.match(/^(\S+) instance launched\s*$/)
          if(match&&Number.isFinite(Date.parse(match[1]))){launched=new Date(match[1]).toISOString();break}
        }
        return [{run,path:rel,file:basename(path),launched,mtime:statSync(path).mtimeMs}]
      }],
      identities:['runs/*/{run.json,settings.json}',path=>{
        const {rel,run}=located(path),{body,error}=parsed(path),data=JSON.parse(body??'{}')
        const kind=basename(path),problem=kind==='run.json'?data.params?.['problem-dir']:data.problem_dir
        return [{run,path:rel,kind,body,error,problem:problem==null?null:basename(problem)}]
      }],
      documents: ['runs/*/{run.json,settings.json,windows/*/forks/*/turns/*/metadata.json,advices/*/advice.json,windows/*/forks/*/turns/*/ts/*/attempts/*/{tests,generation}.json}', path => {
        const {rel,run,parts}=located(path),indexed=parts[0]==='windows'
        return [{path:rel,run,kind:basename(rel),...parsed(path),mtime:statSync(path).mtimeMs,
          window:indexed?Number(parts[1]):null,fork:indexed?Number(parts[3]):null,
          turn:indexed?Number(parts[5]):null,sample:parts[6]==='ts'?Number(parts[7]):null,
          attempt:parts[8]==='attempts'?Number(parts[9]):null,advice:parts[0]==='advices'?parts[1]:null}]
      }],
      advice_text:['runs/*/advices/*/advice.txt',path=>{
        const {rel,run,parts}=located(path)
        return [{path:rel,run,advice:parts[1],body:readFileSync(path,'utf8')}]
      }],
      transcript_lines:['runs/*/windows/*/forks/*/{u/transcript.jsonl,turns/*/ts/*/attempts/*/transcripts/*/*.jsonl}',path=>{
        const {rel,run}=located(path),kind=rel.includes('/u/')?'u':'t',bytes=readFileSync(path),rows=[]
        let start=0
        while(start<bytes.length){
          const newline=bytes.indexOf(10,start),end=newline<0?bytes.length:newline,text=bytes.subarray(start,end).toString('utf8')
          const row={run,path:rel,kind,line:rows.length,offset:start,length:end-start,type:'',completion_id:null,cost:null,incomplete:0,billable:0}
          if(text.trim()){
            let record
            try{record=JSON.parse(text)}catch{row.incomplete=1}
            if(record!==undefined){
              row.type=record?.message?.role??record?.role??record?.type??''
              const value=kind==='u' ? record?.usage??(record?.role==='assistant'?{}:null) : record?.type==='message'?record.message?.usage:null
              const cost=typeof value?.cost==='object'?value.cost?.total:value?.cost
              Object.assign(row,{completion_id:record?.completion_id?String(record.completion_id):null,cost:typeof cost==='number'?cost:null,billable:value?1:0})
            }
          }
          rows.push(row)
          start=end+1
        }
        return rows
      }],
    }
    const tables = schema.split(/\n\s*\n/).filter(s=>s.trim()).map(ddl=>{
      const name=ddl.match(/CREATE (?:TABLE|VIEW) (\w+)/i)[1]
      const [glob,onFile]=sources[name] ?? ['',()=>[]]
      return {name,ddl,glob,onFile}
    })
    this.db = new DirSQL({root:this.root,noIgnore:true,tables,ignore:['**/src/**']})
    this.pending = Promise.resolve()
  }
  // The native connection is shared; serialize statements as in Database.py.
  query(sql, params) {
    const result = this.pending.then(()=>this.db.query(sql,params))
    this.pending = result.then(()=>undefined,()=>undefined)
    return result
  }
  async files(pattern, {content=false}={}) {
    return this.query(`SELECT path, size, mtime${content ? ', content' : ''} FROM ${quote(pattern.startsWith('/')?pattern:'./'+pattern)} ORDER BY path`)
  }
  async close() {await this.pending;await this.db.ready;this.db.close()}
}

export {quote}
