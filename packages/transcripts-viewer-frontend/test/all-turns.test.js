import test from 'node:test'
import assert from 'node:assert/strict'
import {createRunChartData,createForkChartData} from '../src/graphs.js'
test('run lines contain only their own window scores, include failed scores in domain, and preserve gaps in depth',()=>{
 const row={id:'run',problem:'1',strategy:'characters',turns:43,windowPositions:[{id:0,depth:0},{id:1,depth:40}],forks:[
  {window:0,id:0,turns:40,passing:[[38,8]],scored:[[38,8,true],[39,30,false]]},
  {window:0,id:1,turns:2,passing:[[1,5]],scored:[[1,5,true]]},
  {window:1,id:0,turns:43,passing:[[41,6]],scored:[[42,25,false],[41,6,true]]}]}
 const chart=createRunChartData(row)
 assert.deepEqual(chart.windowPositions,[{id:0,depth:0},{id:1,depth:40}])
 assert.equal(chart.series.length,3)
 assert.deepEqual(chart.series[0].scored,[[38,8,true],[39,30,false]])
 assert.deepEqual(chart.series[2].scored,[[41,6,true],[42,25,false]])
 assert.equal(chart.series[2].startPoint,undefined)
 assert.equal(chart.domains.advice.y[1],31.5)
 assert.deepEqual(chart.domains.advice.x,[0,45])
 assert.deepEqual(createForkChartData(row).series[0].advice,[[38,8]])
 assert.equal(createForkChartData(row).domains.advice.y[1],8.4)
})

test('four parallel forks alternate with one solo fork across windows',()=>{
 const forks=[]
 for(const window of [0,1,2])for(const id of [0,1,2,3]){
  const depths=Array.from({length:id===1?20:10},(_,i)=>window*20+i)
  forks.push({window,id,turns:depths.at(-1)+1,passing:[],scored:depths.map(depth=>[depth,100-depth,true])})
 }
 const chart=createRunChartData({id:'run',strategy:'characters',problem:'1',turns:60,forkTurns:10,soloTurns:10,forks})
 assert.equal(chart.series.length,12)
 const paths=chart.series.map(s=>s.scored)
 for(const [depth,count] of [[5,4],[15,1],[25,4],[35,1],[45,4],[55,1]]){
  assert.equal(paths.filter(ps=>ps.some((p,i)=>i>0 && ps[i-1][0]<depth && p[0]>=depth)).length,count)
 }
 for(const series of chart.series){
  assert.equal(series.startPoint,undefined)
  assert.equal(series.scored[0][0],series.window*20)
 }
})
