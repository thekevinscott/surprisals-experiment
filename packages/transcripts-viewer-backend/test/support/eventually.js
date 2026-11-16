import {setTimeout} from 'node:timers/promises'

// Dirsql main applies filesystem events asynchronously; a write completing
// does not mean the index has received it yet. Still fail if it never arrives.
export async function eventually(check) {
  const deadline=performance.now()+3000
  for(;;){
    try{return await check()}
    catch(error){if(performance.now()>=deadline)throw error;await setTimeout(20)}
  }
}
