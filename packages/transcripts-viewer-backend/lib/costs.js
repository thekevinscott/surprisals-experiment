import {readFileSync} from 'node:fs'

const sql=readFileSync(new URL('./costs.sql',import.meta.url),'utf8')
export async function costSnapshot(db,now=Date.now()) {
  const [{payload}]=await db.query(sql,{now})
  return JSON.parse(payload)
}
