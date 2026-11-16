import {mkdtemp,rm,readFile} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {ExperimentDatabase} from '../../lib/experiment-database.js'
const sql=await readFile(new URL('../../lib/charts.sql',import.meta.url),'utf8')
export async function charts(row){
 const root=await mkdtemp(join(tmpdir(),'viewer-charts-')),db=new ExperimentDatabase(root)
 try{const [{payload}]=await db.query(sql,{row:JSON.stringify(row)});return JSON.parse(payload)}
 finally{await db.close();await rm(root,{recursive:true,force:true})}
}
