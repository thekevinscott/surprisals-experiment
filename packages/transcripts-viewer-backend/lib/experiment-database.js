import {DirSQL} from 'dirsql'
import {readFileSync,createReadStream} from 'node:fs'
import {createInterface} from 'node:readline'
import {dirname, basename, relative, resolve, join} from 'node:path'

// Only the turn index is relational; display artifacts remain parsed source files.
const schema = readFileSync(new URL('./schema.sql', import.meta.url), 'utf8')
const TURN = 'windows/*/forks/*/turns/*'
const parse = path => JSON.parse(readFileSync(path, 'utf8'))
const quote = value => `'${value.replaceAll("'", "''")}'`

export class ExperimentDatabase {
  constructor(root, {relations = true} = {}) {
    this.root = resolve(root)
    const rel = path => relative(this.root, path)
    const parent = path => dirname(rel(path))
    const sources = {
      turns: [`${TURN}/metadata.json`, path => {
        const id = parent(path)
        // Parse even though the columns come from the path: malformed metadata
        // must not silently appear to be a complete turn.
        parse(path)
        return [{id, fork_id:dirname(dirname(id)), position:Number(basename(id))}]
      }],
    }
    const tables = relations ? schema.split(';').filter(s=>s.trim()).map(ddl=>{
      const name=ddl.match(/CREATE (?:TABLE|VIEW) (\w+)/i)[1]
      const [glob,onFile]=sources[name] ?? ['',()=>[]]
      return {name,ddl,glob,onFile}
    }) : []
    this.db = new DirSQL({root:this.root,noIgnore:true,tables})
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
  async usage(path, select) {
    const full=join(this.root,path)
    const value={records:[],incomplete:false}
    const lines=createInterface({input:createReadStream(full),crlfDelay:Infinity})
    for await(const line of lines){
      if(!line.trim())continue
      let record
      try{record=JSON.parse(line)}catch{value.incomplete=true;continue}
      const usage=select(record)
      if(usage)value.records.push({id:record.completion_id,cost:typeof usage.cost==='object'?usage.cost?.total:usage.cost})
    }
    return value
  }
  async close() {await this.pending;await this.db.ready;this.db.close()}
}

export async function withDatabase(root, database, work, options) {
  if(database)return work(database)
  const db=new ExperimentDatabase(root,options)
  try{return await work(db)}finally{await db.close()}
}
