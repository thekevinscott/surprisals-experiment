import test from 'node:test'
import assert from 'node:assert/strict'
import {effectScope,nextTick,ref} from 'vue'
import {router} from '../src/router.js'
import {useJsonQuery,clearQueries} from '../src/composables/queryState.js'
const flush=async()=>{await nextTick();await new Promise(resolve=>setImmediate(resolve))}
test('VueUse batches query updates, omits defaults, rebinds keys and restores structured state',async()=>{
 await router.push('/run/example')
 const scope=effectScope(),key=ref('panel:/graphs')
 const [panel,range]=scope.run(()=>[useJsonQuery(key,true),useJsonQuery('chart:x',null)])
 panel.value=false;range.value=[2,8];await flush()
 assert.equal(router.currentRoute.value.query['panel:/graphs'],'false')
 assert.equal(router.currentRoute.value.query['chart:x'],'[2,8]')
 panel.value=true;await flush();assert.equal(router.currentRoute.value.query['panel:/graphs'],undefined)
 key.value='panel:other';panel.value=false;await flush();assert.equal(router.currentRoute.value.query['panel:other'],'false')
 await router.replace({query:{'chart:x':'[3,9]','panel:other':'bad'}})
 assert.deepEqual(range.value,[3,9]);assert.equal(panel.value,true)
 clearQueries(k=>k.startsWith('chart:'));await flush();assert.equal(router.currentRoute.value.query['chart:x'],undefined)
 scope.stop()
})
