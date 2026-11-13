import test from 'node:test'
import assert from 'node:assert/strict'
import {createServer} from 'vite'
import vue from '@vitejs/plugin-vue'
import {createSSRApp,h} from 'vue'
import {renderToString} from 'vue/server-renderer'
const decode=s=>s.replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&')
test('advice tokens preserve exact text and expose each token surprisal rounded to three decimals',async()=>{
 const server=await createServer({configFile:false,optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true,ws:false},plugins:[vue()]})
 try{
  const {default:TokenText}=await server.ssrLoadModule('/src/components/TokenText.vue')
  const tokens=[['Read',0],['  <input> &',8.08],['\n\n',1.25],['😀',3.512345],['',2]],text=tokens.map(t=>t[0]).join('')
  const render=props=>renderToString(createSSRApp({render:()=>h(TokenText,props)}))
  const html=await render({text,tokens}),spans=[...html.matchAll(/<span\b([^>]*)>([\s\S]*?)<\/span>/g)]
  assert.equal(spans.length,tokens.length)
  assert.equal(spans.map(s=>decode(s[2])).join(''),text)
  assert.deepEqual(spans.map(s=>decode(s[1].match(/aria-label="([^"]*)"/)[1])),tokens.map(([,bits])=>`${Number(bits.toFixed(3))} bits`))
  const plain=await render({text});assert(!plain.includes('<span'));assert.equal(decode(plain.replace(/<!--[\s\S]*?-->/g,'')),text)
 }finally{await server.close()}
})
