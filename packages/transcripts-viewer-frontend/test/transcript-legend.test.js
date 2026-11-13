import test from 'node:test'
import assert from 'node:assert/strict'
import {createServer} from 'vite'
import vue from '@vitejs/plugin-vue'
import {createSSRApp,h} from 'vue'
import {renderToString} from 'vue/server-renderer'

test('transcript legend defaults hide only session/model/thinking changes and preserve source numbering',async()=>{
 const server=await createServer({configFile:false,optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true,ws:false},plugins:[{name:'record-stub',enforce:'pre',transform(code,id){if(id.endsWith('/TranscriptRecord.vue'))return '<script setup>defineProps({message:Object})</script><template><p>{{message.raw}}</p></template>'}},vue()]})
 try{
  const {default:View}=await server.ssrLoadModule('/src/components/TranscriptView.vue')
  const roles=['session','model_change','thinking_level_change','system','user','assistant','toolResult','new_type']
  const html=await renderToString(createSSRApp({render:()=>h(View,{messages:roles.map((role,index)=>({role,line:index+1,raw:role}))})}))
  const inputs=[...html.matchAll(/<input\b[^>]*>/g)].map(m=>m[0]);assert.equal(inputs.length,roles.length)
  assert.deepEqual(inputs.map(input=>/\bchecked(?:\s|>|=)/.test(input)),roles.map((_,i)=>i>=3))
  assert.deepEqual([...html.matchAll(/data-block="(\d+)"/g)].map(m=>Number(m[1])),[4,5,6,7,8])
  assert.equal([...html.matchAll(/aria-label="Jump to /g)].length,5)
 }finally{await server.close()}
})
