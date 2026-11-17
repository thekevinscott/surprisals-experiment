import {DirSQL} from 'dirsql'
import {readFileSync,statSync} from 'node:fs'
import {dirname, basename, relative, resolve} from 'node:path'

const schema = readFileSync(new URL('./schema.sql', import.meta.url), 'utf8')
const quote = value => `'${value.replaceAll("'", "''")}'`

export class ExperimentDatabase {
  constructor(root, {relations = true} = {}) {
    this.root = resolve(root)
    const sources = {
      pod_records:['runpod-costs/*.json',path=>{
        const {id,gpu,costPerHr,start,stop}=JSON.parse(readFileSync(path,'utf8'))
        return [{path:relative(this.root,path),id,gpu,costPerHr,start,stop}]
      }],
      launch_events:['stderr-*.txt',path=>{
        for(const line of readFileSync(path,'utf8').split('\n')){
          const match=line.match(/^(\S+) instance launched\s*$/)
          if(match&&Number.isFinite(Date.parse(match[1])))return [{path:relative(this.root,path),launched:new Date(match[1]).toISOString()}]
        }
        return []
      }],
      identities:['{run.json,settings.json,runs/*/run.json,runs/*/settings.json}',path=>{
        const body=readFileSync(path,'utf8')
        let data
        try{data=JSON.parse(body)}catch(error){throw Error(`Cannot read ${path}: ${error.message}`)}
        const kind=basename(path),problem=kind==='run.json'?data.params?.['problem-dir']:data.problem_dir
        return [{id:basename(dirname(path)),path:relative(this.root,path),kind,body,problem:problem==null?null:basename(problem)}]
      }],
      documents: ['', path => {
        const rel=relative(this.root,path),parts=rel.split('/'),body=readFileSync(path,'utf8')
        try{JSON.parse(body)}catch(error){throw Error(`Cannot read ${path}: ${error.message}`)}
        const indexed=parts[0]==='windows'
        return [{path:rel,parent:dirname(rel),kind:basename(rel),body,mtime:statSync(path).mtimeMs,
          window:indexed?Number(parts[1]):null,fork:indexed?Number(parts[3]):null,
          turn:indexed?Number(parts[5]):null,sample:parts[6]==='ts'?Number(parts[7]):null,
          attempt:parts[8]==='attempts'?Number(parts[9]):null}]
      }],
      advice_text:['advices/*/advice.txt',path=>[{path:relative(this.root,path),body:readFileSync(path,'utf8')}]],
    }
    sources.documents[0]='{run.json,settings.json,windows/*/forks/*/turns/*/metadata.json,advices/*/advice.json,windows/*/forks/*/turns/*/ts/*/attempts/*/{tests,generation}.json}'
    const tables = schema.split(';').filter(s=>s.trim()).filter(ddl=>relations||/CREATE TABLE (identities|pod_records)/.test(ddl)).map(ddl=>{
      const name=ddl.match(/CREATE (?:TABLE|VIEW) (\w+)/i)[1]
      const [glob,onFile]=sources[name] ?? ['',()=>[]]
      return {name,ddl,glob,onFile}
    })
    this.db = new DirSQL({root:this.root,noIgnore:true,tables,ignore:relations?[]:['**/windows/**','**/advices/**']})
    this.pending = Promise.resolve()
  }
  // The native connection is shared; serialize statements as in Database.py.
  query(sql, params) {
    const result = this.pending.then(()=>this.db.query(sql,params))
    this.pending = result.then(()=>undefined,()=>undefined)
    return result
  }
  async files(pattern, {content=false}={}) {
    return this.query(`SELECT path, size, mtime${content ? ', content' : ''} FROM ${quote('./'+pattern)} ORDER BY path`)
  }
  async text(path, optional=false) {
    // Exact source paths may contain glob metacharacters. Filter the parent
    // directory's rows using a bound path, never interpolate user data into SQL.
    const full=resolve(path), rel=relative(this.root,full)
    const folder=dirname(rel)==='.' ? './' : './'+dirname(rel)+'/'
    const rows=await this.query(`SELECT content FROM ${quote(folder)} WHERE path = ?`,[rel])
    if (!rows.length) {
      if(optional)return null
      throw Object.assign(new Error(`Cannot read ${full}: ENOENT`),{code:'ENOENT'})
    }
    if(rows[0].content==null)throw Error(`Cannot read ${full}`)
    return rows[0].content
  }
  async json(path, optional=false) {
    const text=await this.text(path,optional)
    if(text===null)return null
    try{return JSON.parse(text)}catch(error){throw Error(`Cannot read ${path}: ${error.message}`)}
  }
  async close() {await this.costs?.close();await this.pending;await this.db.ready;this.db.close()}
}

export async function withDatabase(root, database, work, options) {
  if(database)return work(database)
  const db=new ExperimentDatabase(root,options)
  try{return await work(db)}finally{await db.close()}
}
