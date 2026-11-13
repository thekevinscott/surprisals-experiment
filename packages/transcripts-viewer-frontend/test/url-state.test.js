import test from 'node:test'
import assert from 'node:assert/strict'
import {readState,stateHash} from '../src/composables/urlState.js'
test('URL state preserves route and other controls, omits defaults, round-trips values',()=>{
 const hash=stateHash('#run/example?other=1','panel:/graphs',false,true)
 assert.equal(readState(hash,'panel:/graphs',true),false)
 assert.equal(readState(hash,'other',0),1)
 assert.equal(stateHash(hash,'panel:/graphs',true,true),'#run/example?other=1')
 const zoom=stateHash(hash,'chart:x',[2,8],null)
 assert.deepEqual(readState(zoom,'chart:x',null),[2,8])
 assert.equal(readState('#dashboard?bad=oops','bad',true),true)
})
