import test from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import {createServer} from 'vite'
import vue from '@vitejs/plugin-vue'
import {createSSRApp,h} from 'vue'
import {renderToString} from 'vue/server-renderer'

const decode=html=>html.replace(/<!--[\s\S]*?-->/g,'').replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&')
test('real U transcript renders every source field and exposes reasoning as its own block',async()=>{
  // Stub only panel chrome: capture metadata passed to its existing popover.
  // TranscriptRecord, TextSection and TokenText are the real compiled components.
  const server=await createServer({configFile:false,optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true},plugins:[{
    name:'panel-test-chrome',enforce:'pre',transform(code,id){if(id.endsWith('/ContentPanel.vue'))return `<script setup>defineProps({title:String,metadata:Object})</script><template><section><header>{{title}}</header><aside class="record-metadata">{{JSON.stringify(metadata)}}</aside><slot :expanded="true" /></section></template>`},
  },vue()]})
  try{
    const {default:Record}=await server.ssrLoadModule('/src/components/TranscriptRecord.vue')
    const raw=await readFile(new URL('./fixtures/lucky-sunset-u.jsonl',import.meta.url),'utf8')
    for(const [index,line] of raw.split('\n').entries()){
      if(!line)continue
      const source=JSON.parse(line)
      const html=await renderToString(createSSRApp({render:()=>h(Record,{label:source.role,message:{raw:line,line:index+1},contentOnly:true})}))
      const metadataText=decode(html.match(/<aside class="record-metadata">([\s\S]*?)<\/aside>/)[1])
      const metadata=metadataText?JSON.parse(metadataText):{}
      const body=decode(html.match(/<p(?:\s[^>]*)?>([\s\S]*?)<\/p>/)?.[1]??'')
      const represented={...metadata}
      if('role' in source){assert.ok(html.includes(`<header>${source.role}</header>`));represented.role=source.role}
      if('content' in source)represented.content=typeof source.content==='string'?body:JSON.parse(body)
      assert.deepEqual(represented,source,`every key on physical line ${index+1} must remain represented`)
      if(typeof source.reasoning==='string' && source.reasoning){
        const reasoning=html.match(/<details[^>]*class="record-reasoning"[^>]*>[\s\S]*?<pre[^>]*>([\s\S]*?)<\/pre>/)
        assert.ok(reasoning,`line ${index+1} needs an independent reasoning block`)
        assert.equal(decode(reasoning[1]),source.reasoning)
      }
    }
  }finally{await server.close()}
})
