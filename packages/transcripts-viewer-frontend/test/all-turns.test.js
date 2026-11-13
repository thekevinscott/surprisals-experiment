import test from 'node:test'
import assert from 'node:assert/strict'
import {createRunChartData,createForkChartData} from '../src/graphs.js'
test('run lines join the same fork across windows, include failed scores in domain, and preserve gaps in depth',()=>{
 const row={id:'run',problem:'1',strategy:'characters',turns:43,windowPositions:[{id:0,depth:0},{id:1,depth:40}],forks:[
  {window:0,id:0,turns:40,passing:[[38,8]],scored:[[38,8,true],[39,30,false]]},
  {window:0,id:1,turns:2,passing:[[1,5]],scored:[[1,5,true]]},
  {window:1,id:0,turns:43,passing:[[41,6]],scored:[[42,25,false],[41,6,true]]}]}
 const chart=createRunChartData(row)
 assert.deepEqual(chart.windowPositions,[{id:0,depth:0},{id:1,depth:40}])
 assert.equal(chart.series.length,2)
 assert.deepEqual(chart.series[0].scored,[[38,8,true],[39,30,false],[41,6,true],[42,25,false]])
 assert.equal(chart.domains.advice.y[1],31.5)
 assert.deepEqual(chart.domains.advice.x,[0,45])
 assert.deepEqual(createForkChartData(row).series[0].advice,[[38,8]])
 assert.equal(createForkChartData(row).domains.advice.y[1],8.4)
})
