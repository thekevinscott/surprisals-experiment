import test from 'node:test'
import assert from 'node:assert/strict'
import {createForkChartData} from '../src/graphs.js'

test('fork charts preserve fork identity, true depth, and independent best scores', () => {
  const data = createForkChartData({id:'run',problem:'0054',strategy:'characters',turns:44,ended:'done',exit:0,
    forks:[
      {window:0,id:0,turns:3,passing:[[0,20],[1,25],[2,10]]},
      {window:0,id:2,turns:3,passing:[[0,15],[2,12]]},
      {window:1,id:0,turns:44,passing:[[42,9],[43,8]]},
      {window:1,id:2,turns:44,passing:[]},
    ]})
  assert.deepEqual(data.series.map(s=>s.advice), [[[0,20],[2,10]],[[0,15],[2,12]],[[42,9],[43,8]],[]])
  assert.deepEqual(data.series.map(s=>s.label), ['Window 0 · Fork 0','Window 0 · Fork 2','Window 1 · Fork 0','Window 1 · Fork 2'])
  assert.equal(new Set(data.series.map(s=>s.cell)).size,4)
  assert.equal(new Set(data.series.map(s=>s.color)).size,4)
  assert.deepEqual(data.series[0].passing,[[0,20],[1,25],[2,10]])
  assert.deepEqual(data.domains.advice.x,[0,46])
  assert.equal(data.domains.advice.y[1],26.25)
})

test('empty fork charts retain a valid domain', () => {
  assert.deepEqual(createForkChartData({forks:[]}).series,[])
})
