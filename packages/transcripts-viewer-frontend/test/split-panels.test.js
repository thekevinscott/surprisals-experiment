import test from 'node:test'
import assert from 'node:assert/strict'
import {snapPanelSizes} from '../src/composables/snapPanelSizes.js'

test('graph and transcript panels snap below 15%, retain the boundary, and reopen',()=>{
  for(const [sizes,expected] of [
    [[50,50],[50,50]],[[14,86],[0,100]],[[15,85],[15,85]],
    [[85,15],[85,15]],[[86,14],[100,0]],[[0,100],[0,100]],
    [[100,0],[100,0]],[[20,80],[20,80]],[[80,20],[80,20]],
    [[10,80],[0,100]],[[80,10],[100,0]],[[40,40],[50,50]],
  ])assert.deepEqual(snapPanelSizes(sizes),expected)
})
