import test from 'node:test'
import assert from 'node:assert/strict'
import {createServer} from 'vite'
import vue from '@vitejs/plugin-vue'
import {createSSRApp,h} from 'vue'
import {renderToString} from 'vue/server-renderer'

test('T renders every attempt tests in order with independent original-file targets, including empty cases',async()=>{
  const attempts=[
    {id:0,tests:{passed:0,total:1,cases:[{index:0,status:'provider_error'}]}},
    {id:2,tests:{passed:0,total:0,cases:[]}},
    {id:10,tests:{passed:1,total:1,cases:[{index:0,status:'passed'}]}},
  ].map(attempt=>({...attempt,testsSource:`turns/0/ts/0/attempts/${attempt.id}/tests.json`,files:[],transcriptFiles:[]}))
  const server=await createServer({configFile:false,optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true,ws:false},plugins:[{
    name:'sample-test-data',enforce:'pre',transform(code,id){
      if(id.endsWith('/ContentPanel.vue'))return '<script setup>defineProps({title:String})</script><template><section><slot /></section></template>'
      if(id.endsWith('/composables/api.js'))return `import {ref} from 'vue';export const fetchJson=()=>{};export const useLiveResource=()=>({data:ref(${JSON.stringify({attempts})}),loading:ref(false),error:ref('')});`
    },
  },vue()]})
  try{
    const {default:Sample}=await server.ssrLoadModule('/src/components/TSample.vue')
    const app=createSSRApp({render:()=>h(Sample,{sample:{id:0,source:'turns/0/ts/0',latest:attempts.at(-1)}})})
    app.provide('apiUrl',source=>`/api/${source}`)
    app.provide('rawSourceUrl',source=>`/api/files/${source}`)
    app.provide('sourceUrl',source=>`#/files/${source}?src=/api/files/${source}`)
    const html=await renderToString(app)
    assert.deepEqual([...html.matchAll(/data-attempt="(\d+)"/g)].map(match=>Number(match[1])),[0,2,10])
    assert.ok(html.includes('/attempts/2/tests.json'),'empty test cases still link to their original tests file')
    assert.ok(!html.includes('attempt-label'),'attempt labels are omitted')
    assert.ok(html.includes('data-status="provider_error"'))
    assert.ok(html.includes('data-status="passed"'))
  }finally{await server.close()}
})
