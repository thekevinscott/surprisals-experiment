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
  const html=await render({text,tokens}),spans=[...html.matchAll(/<span\b([^>]*aria-label="[^"]*"[^>]*)>/g)]
  assert.equal(spans.length,tokens.length)
  assert.equal(decode(html.replace(/<!--[\s\S]*?-->|<[^>]+>/g,'')),text)
  assert.deepEqual(spans.map(s=>decode(s[1].match(/aria-label="([^"]*)"/)[1])),tokens.map(([,bits])=>`${Number(bits.toFixed(3))} bits`))
  const plain=await render({text});assert(!plain.includes('aria-label'));assert.equal(decode(plain.replace(/<!--[\s\S]*?-->|<[^>]+>/g,'')),text)
  const highlighted=await render({text,tokens,additions:[[2,10]]});assert(highlighted.includes('advice-added'));assert.equal(decode(highlighted.replace(/<!--[\s\S]*?-->|<[^>]+>/g,'')),text);assert.equal((highlighted.match(/aria-label=/g)||[]).length,tokens.length)
 }finally{await server.close()}
})
