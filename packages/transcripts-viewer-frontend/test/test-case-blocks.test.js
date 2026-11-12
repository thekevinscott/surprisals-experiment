import test from 'node:test'
import assert from 'node:assert/strict'
import {testCaseBlocks} from '../src/composables/outcomes.js'

test('test blocks use only actual cases and preserve statuses without deriving outcomes from passed', () => {
  const cases = [{index:10,passed:false,status:'timed_out'},{index:3,passed:true,status:'provider_error'},{index:21,passed:false,status:'passed'},{index:22,passed:false}]
  assert.deepEqual(testCaseBlocks(cases), [
    {status:'timed_out',index:10,position:0},
    {status:'provider_error',index:3,position:1},
    {status:'passed',index:21,position:2},
    {status:undefined,index:22,position:3},
  ])
  assert.deepEqual(testCaseBlocks(undefined),[])
})
