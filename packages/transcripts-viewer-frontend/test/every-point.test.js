import test from 'node:test'
import assert from 'node:assert/strict'
import {createServer} from 'vite'
import vue from '@vitejs/plugin-vue'
import {createSSRApp,h} from 'vue'
import {renderToString} from 'vue/server-renderer'
import {createChartData} from '../src/graphs.js'

test('top advice line connects every passing score in turn order without changing best/wait data',async()=>{
 const data=createChartData([{id:'run',problem:'1958',strategy:'characters',turns:43,ended:'done',passing:[[0,20],[1,25],[2,10],[3,15],[42,12]]}])
 assert.deepEqual(data.series[0].advice,[[0,20],[2,10]])
 assert.deepEqual(data.wait[0].bests,[[2,10,2]]);assert.deepEqual(data.wait[0].pending,[10,40])
 data.series[0].passing.reverse();const original=structuredClone(data)
 const server=await createServer({configFile:false,optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true,ws:false},plugins:[vue()]})
 try{
  const {default:Chart}=await server.ssrLoadModule('/src/components/CellChart.vue')
  const render=allPoints=>renderToString(createSSRApp({render:()=>h(Chart,{chartData:data,kind:'advice',allPoints})}))
  const html=await render(true),path=html.match(/<path[^>]* d="([^"]*)"/)?.[1]??html.match(/<path d="([^"]*)"/)?.[1]
  const expected=[[0,20],[1,25],[2,10],[3,15],[42,12]].map(([x,y],i)=>`${i?'L':'M'}${x/45*840},${240-y/26.25*210}`).join(' ')
  assert.equal(path,expected,'rising, falling and later-window points remain at original depths')
  assert.match(await render(false),/H/,'existing running-best step mode remains available')
  assert.deepEqual(data,original,'chart rendering does not alter improvement/wait calculations')
 }finally{await server.close()}
})
