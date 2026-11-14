import test from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import {compile,createSSRApp} from 'vue'
import {renderToString} from 'vue/server-renderer'
import {router} from '../src/router.js'

test('cost badges appear only on the dashboard with no file open',async()=>{
  const source=await readFile(new URL('../src/App.vue',import.meta.url),'utf8')
  const render=compile(source.match(/<RunpodCost\b[^>]*\/>/)[0])
  for(const path of ['/dashboard','/graphs','/run/r','/run/r/window/0','/run/r/window/0/fork/0','/run/r/window/0/fork/0/turn/0','/files/test.txt']){
    for(const filePreview of [null,{name:'test.txt'}]){
      const route=router.resolve(path)
      const html=await renderToString(createSSRApp({
        components:{RunpodCost:{template:'<aside>RunPod total</aside>'}},
        setup:()=>({route,filePreview,now:0,target:route.meta.run?route.params:null,fileRoute:route.name==='file',tab:route.name==='graphs'?'graphs':'dashboard'}),
        render,
      }))
      assert.equal(html.includes('RunPod total'),route.name==='dashboard'&&!filePreview,`${path}, file open: ${!!filePreview}`)
    }
  }
})
