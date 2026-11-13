import {createReadStream} from 'node:fs'
import {createInterface} from 'node:readline'
import {join} from 'node:path'

export async function instanceLaunch(directory,database) {
  let earliest=null
  for(const {path} of await database.files('stderr-*.txt')) {
    const stream=createReadStream(join(directory,path))
    const lines=createInterface({input:stream,crlfDelay:Infinity})
    try {
      for await(const line of lines) {
        const match=line.match(/^(\S+) instance launched\s*$/)
        if(!match || !Number.isFinite(Date.parse(match[1])))continue
        const time=Date.parse(match[1])
        if(earliest===null || time<earliest)earliest=time
        break
      }
    } finally { lines.close();stream.destroy() }
  }
  return earliest===null ? null : new Date(earliest).toISOString()
}
