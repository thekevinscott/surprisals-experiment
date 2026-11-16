import {withDatabase} from './experiment-database.js'

export async function readRunpodCosts(directory,database) {
  if(!database)return withDatabase(directory,null,db=>readRunpodCosts(directory,db),{relations:false})
  return database.query('SELECT id,gpu,costPerHr,start,stop FROM pod_records ORDER BY path')
}
