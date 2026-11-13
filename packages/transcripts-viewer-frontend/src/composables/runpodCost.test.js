import test from 'node:test'
import assert from 'node:assert/strict'
import {runpodCost,runpodTooltip} from './runpodCost.js'
test('RunPod totals include completed and live pods once each',()=>{
  const pods=[{id:'a',gpu:'H100',costPerHr:2,start:'2026-11-13T00:00:00Z',stop:'2026-11-13T01:00:00Z'},
    {id:'b',gpu:'H200',costPerHr:3,start:'2026-11-13T01:00:00Z',stop:null}]
  assert.equal(runpodCost(pods,Date.parse('2026-11-13T03:00:00Z')),8)
  assert.equal(runpodCost(pods,Date.parse('2026-11-13T04:00:00Z')),11)
  assert.equal(runpodCost([],Date.now()),0)
  assert.match(runpodTooltip(pods),/a · H100 · \$2\/hr/)
  assert.match(runpodTooltip(pods),/Stop: live/)
})
