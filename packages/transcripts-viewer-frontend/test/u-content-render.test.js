import test from 'node:test'
import assert from 'node:assert/strict'
import {createServer} from 'vite'
import vue from '@vitejs/plugin-vue'
import {createSSRApp,h} from 'vue'
import {renderToString} from 'vue/server-renderer'
const decode=s=>s.replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&')
test('U renders exact reasoning before exact content, and system/user content without metadata',async()=>{
 const server=await createServer({configFile:false,optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true,ws:false},plugins:[{name:'panel-chrome',enforce:'pre',transform(code,id){if(id.endsWith('/ContentPanel.vue'))return '<script setup>defineProps({title:String})</script><template><section><h3>{{title}}</h3><slot /></section></template>'}},vue()]})
 try{
  const {default:Record}=await server.ssrLoadModule('/src/components/TranscriptRecord.vue')
  const render=record=>renderToString(createSSRApp({render:()=>h(Record,{uView:true,label:'3',message:{raw:JSON.stringify(record)}})}))
  const content='  Reply <exact> & unchanged\n\n',reasoning='Reasoning\n  with spacing\n'
  const html=await render({role:'assistant',content,reasoning,reasoning_details:[{text:reasoning}],usage:{cost:42}})
  assert.deepEqual([...html.matchAll(/<p[^>]*>([\s\S]*?)<\/p>/g)].map(m=>decode(m[1])),[reasoning,content])
  assert.match(html,/reasoning<\/h3>/);assert(!html.includes('usage'))
  for(const role of ['system','user'])assert.deepEqual([...((await render({role,content})).matchAll(/<p[^>]*>([\s\S]*?)<\/p>/g))].map(m=>decode(m[1])),[content])
 }finally{await server.close()}
})
