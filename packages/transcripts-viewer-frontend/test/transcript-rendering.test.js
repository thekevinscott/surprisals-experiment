import test from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import {createServer} from 'vite'
import vue from '@vitejs/plugin-vue'
import {createSSRApp,h} from 'vue'
import {renderToString} from 'vue/server-renderer'

const decode=html=>html.replace(/<!--[\s\S]*?-->/g,'').replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&')
test('every real transcript line renders raw without dropping or rewriting any field',async()=>{
  const server=await createServer({configFile:false,optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true},plugins:[{
    name:'panel-test-chrome',enforce:'pre',transform(code,id){if(id.endsWith('/ContentPanel.vue'))return `<script setup>defineProps({title:String,source:String,sourceLine:Number})</script><template><section :data-source="source" :data-line="sourceLine"><slot :expanded="true" /></section></template>`},
  },vue()]})
  try{
    const {default:Record}=await server.ssrLoadModule('/src/components/TranscriptRecord.vue')
    const raw=await readFile(new URL('./fixtures/lucky-sunset-u.jsonl',import.meta.url),'utf8')
    const lines=raw.split('\n');if(lines.at(-1)==='')lines.pop()
    lines.push('', 'broken', '{"type":"session","version":3}', '{"type":"message","message":{"role":"system","sections":[{"text":"system prompt"}]}}')
    for(const [index,line] of lines.entries()){
      const html=await renderToString(createSSRApp({render:()=>h(Record,{label:String(index+1),message:{raw:line,source:'u/transcript.jsonl',line:index+1},contentOnly:true})}))
      const body=decode(html.match(/<p(?:\s[^>]*)?>([\s\S]*?)<\/p>/)?.[1]??'')
      assert.equal(body,line,`physical line ${index+1} remains verbatim`)
      assert.ok(html.includes('data-source="u/transcript.jsonl"'))
      if(line.startsWith('{'))assert.deepEqual(JSON.parse(body),JSON.parse(line),'every source key remains visible')
    }
  }finally{await server.close()}
})
