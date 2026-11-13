import test from 'node:test'
import assert from 'node:assert/strict'
import {experimentCost,costTooltip} from './experimentCost.js'
test('total sums all runs and adds shared pods once, with live compute ticking',()=>{
  const rows=[{uCost:1,tCost:2,awsLaunched:'2026-11-13T00:00:00Z',ended:'2026-11-13T01:00:00Z'},
    {uCost:3,tCost:4,awsLaunched:'2026-11-13T00:00:00Z'}]
  const pods=[{costPerHr:2,start:'2026-11-13T00:00:00Z',stop:null}]
  const result=experimentCost(rows,pods,Date.parse('2026-11-13T02:00:00Z'))
  assert.equal(result.u,4);assert.equal(result.t,6);assert.equal(result.aws,0.3024);assert.equal(result.runpod,4)
  assert.equal(result.total,14.3024)
  assert.ok(experimentCost(rows,pods,Date.parse('2026-11-13T03:00:00Z')).total>result.total)
  assert.match(costTooltip(result,pods),/U: \$4.00\nT: \$6.00\nAWS estimate \(compute only\): \$0.30\nRunPod estimate \(compute only\): \$4.00/)
})
test('missing costs are excluded and explained, not silently presented as complete',()=>{
  const result=experimentCost([{uCost:null,tCost:1}],[],Date.now())
  assert.equal(result.total,1)
  assert.match(costTooltip(result,[],['Partial usage']),/U: \$0.00 \(1 runs unavailable; excluded\)/)
  assert.match(costTooltip(result,[]),/no pod records/)
  assert.match(costTooltip(result,[],['Partial usage']),/Partial usage/)
  assert.equal(experimentCost([],[],Date.now()).total,0)
})
