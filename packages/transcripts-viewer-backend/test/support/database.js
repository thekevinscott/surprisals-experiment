import {ExperimentDatabase} from '../../lib/experiment-database.js'
export function database(t,root){
 const db=new ExperimentDatabase(root)
 t.after(()=>db.close())
 return db
}
export const position=source=>{const [,window,,fork,,turn,,sample]=source.split('/');return {window,fork,turn,sample}}
