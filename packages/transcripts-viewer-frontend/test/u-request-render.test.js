import test from 'node:test'
import assert from 'node:assert/strict'
import {createServer} from 'vite'
import vue from '@vitejs/plugin-vue'
import {createSSRApp,h} from 'vue'
import {renderToString} from 'vue/server-renderer'

test('U modal renders only sent rows and its assistant reply, or sent rows and the recorded error',async()=>{
  const observer=globalThis.IntersectionObserver
  globalThis.IntersectionObserver=class {observe(){} disconnect(){}}
  const server=await createServer({configFile:false,optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true,ws:false},plugins:[{
    name:'request-fixture',enforce:'pre',transform(code,id){
      if(id.endsWith('/composables/api.js'))return `import {ref,onServerPrefetch} from 'vue';
        export const fetchJson=async()=>({blocks:['system','user','assistant','user','assistant'].map((type,index)=>({type,index}))});
        export const watchData=()=>{};
        export function useLiveResource(sources,load){const data=ref(null);onServerPrefetch(async()=>{data.value=await load(new AbortController().signal,sources())});return {data,loading:ref(false),error:ref('')}};`
    },
  },vue()]})
  try{
    const {default:Viewer}=await server.ssrLoadModule('/src/components/TranscriptViewer.vue')
    const render=turnMetadata=>renderToString(createSSRApp({render:()=>h(Viewer,{turnMetadata,source:'u/transcript.jsonl',files:[{source:'u/transcript.jsonl',url:'/api/runs/one/files/u/transcript.jsonl'}],sourceUrl:s=>s})}))
    const count=html=>[...html.matchAll(/data-block="\d+"/g)].length
    assert.equal(count(await render({u_messages:2})),3,'request plus assistant at the boundary')
    const failed=await render({u_messages:3,error:'U failed: token limit'})
    assert.equal(count(failed),3,'non-assistant boundary and later turns excluded')
    assert.match(failed,/U failed: token limit/)
    assert.equal(count(await render({u_messages:0,error:'No request sent'})),0)
    assert.equal(count(await render({})),5,'legacy metadata retains the whole transcript')
  }finally{await server.close();globalThis.IntersectionObserver=observer}
})
