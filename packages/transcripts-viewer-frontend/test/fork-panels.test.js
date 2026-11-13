import test from 'node:test'
import assert from 'node:assert/strict'
import {createServer} from 'vite'
import vue from '@vitejs/plugin-vue'
import {createSSRApp,h,ref} from 'vue'
import {renderToString} from 'vue/server-renderer'
import {createForkPhaseChartData} from '../src/graphs.js'

test('every turn stays noncollapsible and parallel and solo phases get separate charts',async()=>{
 const turn=id=>({id,source:`turns/${id}`,samples:[]})
 const window={id:0,continuedForks:[1],forks:[{id:0,parallel:[turn(0),turn(1),turn(2)],solo:[]},{id:1,parallel:[turn(0),turn(1),turn(2)],solo:[turn(3),turn(4)]}]}
 const run={id:'run',strategy:'characters',problem:'p',forkTurns:3,soloTurns:2,forks:[{window:0,id:0,turns:3,passing:[[0,20],[2,18]]},{window:0,id:1,turns:5,passing:[[0,19],[2,17],[4,12]]}]}
 const server=await createServer({configFile:false,optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true,ws:false},plugins:[{
  name:'fork-panel-stubs',enforce:'pre',transform(code,id){
   if(id.endsWith('/ContentPanel.vue'))return '<script setup>defineProps({title:String,collapsible:{type:Boolean,default:true},expanded:Boolean})</script><template><section :data-collapsible="collapsible" :data-expanded="expanded"><slot /></section></template>'
   if(id.endsWith('/TTranscripts.vue'))return '<template><div /></template>'
   if(id.endsWith('/CellChart.vue'))return '<script setup>defineProps({chartData:Object})</script><template><div class="chart-fixture" :data-series="chartData.series.length" :data-label="chartData.series[0].label" :data-last-depth="chartData.series[0].passing.at(-1)[0]" /></template>'
  },
 },vue()]})
 try{
  const {default:Window}=await server.ssrLoadModule('/src/components/ForkWindow.vue')
  const app=createSSRApp({render:()=>h(Window,{window})})
  app.provide('runLink',source=>'#'+source);app.provide('sampleCount',()=>5);app.provide('sourceUrl',source=>'#'+source)
  app.provide('forkRange',ref(null))
  app.provide('forkChart',(window,id,solo)=>createForkPhaseChartData(run,window,id,solo))
  const html=await renderToString(app)
  const turns=[...html.matchAll(/<section\b[^>]*class="turn-block"[^>]*>/g)].map(match=>match[0])
  assert.equal(turns.length,8)
  assert.ok(turns.every(turn=>turn.includes('data-collapsible="false"')))
  const charts=[...html.matchAll(/<div\b[^>]*class="chart-fixture"[^>]*>/g)].map(match=>match[0])
  assert.equal(charts.length,3)
  assert.ok(charts.every(chart=>chart.includes('data-series="1"')))
  assert.ok(charts[0].includes('data-label="Window 0 · Fork 0"')&&charts[0].includes('data-last-depth="2"'))
  assert.ok(charts[1].includes('data-label="Window 0 · Fork 1"')&&charts[1].includes('data-last-depth="2"')
  &&charts[2].includes('data-last-depth="4"'))
 }finally{await server.close()}
})
