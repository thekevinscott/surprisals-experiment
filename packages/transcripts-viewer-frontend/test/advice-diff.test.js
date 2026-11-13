import test from 'node:test'
import assert from 'node:assert/strict'
import {addedRanges,highlightParts} from '../src/composables/adviceDiff.js'
test('advice additions preserve exact text across token boundaries and exclude deletions',()=>{
 const text='Keep the new words.',ranges=addedRanges('Keep old words.',text)
 const pieces=[...highlightParts('Keep the n',ranges),...highlightParts('ew words.',ranges,10)]
 assert.equal(pieces.map(p=>p.text).join(''),text)
 assert.equal(pieces.filter(p=>p.added).map(p=>p.text).join('').replace(/\s/g,''),'thenew')
 assert.deepEqual(addedRanges('Keep old words.','Keep words.'),[])
})

test('split diff chunks retain source token scores',async()=>{
 const {sliceTokens}=await import('../src/composables/adviceDiff.js')
 assert.deepEqual(sliceTokens([['hello ',2],['world',4]],3,5),[['lo ',2],['wo',4]])
})
