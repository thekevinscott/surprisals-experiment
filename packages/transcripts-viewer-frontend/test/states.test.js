import test from 'node:test'
import assert from 'node:assert/strict'
import {attemptState} from '../src/composables/outcomes.js'
test('timeout, failed tests, missing tests, and success have distinct labels',()=>{
 assert.equal(attemptState({generation:{timed_out:true}}),'Timed out')
 assert.equal(attemptState({generation:{error:'provider failed'}}),'Failed: provider failed')
 assert.equal(attemptState({}),'Tests not recorded')
 assert.equal(attemptState({tests:{passed:0,total:5,all_passed:false}}),'Failed · 0/5 tests passed')
 assert.equal(attemptState({tests:{passed:5,total:5,all_passed:true}}),'Passed · 5/5 tests passed')
})

test('transcript timeout messages preserve recorded details and do not label successful attempts',async()=>{
 const {transcriptFailure}=await import('../src/composables/outcomes.js')
 assert.equal(transcriptFailure({generation:{timed_out:true}}),'Generation timed out before this attempt completed.')
 assert.equal(transcriptFailure({generation:{timed_out:true,error:'Deadline exceeded after 120s'}}),'Generation timed out before this attempt completed.\nDeadline exceeded after 120s')
 assert.equal(transcriptFailure({generation:{timed_out:false}}),null)
})
