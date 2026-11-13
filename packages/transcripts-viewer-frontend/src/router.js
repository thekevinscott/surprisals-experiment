import {createRouter,createWebHashHistory,createMemoryHistory} from 'vue-router'
const component=typeof window==='undefined'?{render:()=>null}:()=>import('./App.vue')
export const router=createRouter({
  history:typeof window==='undefined'?createMemoryHistory():createWebHashHistory(),
  routes:[
    {path:'/',redirect:'/dashboard'},
    {path:'/dashboard',name:'dashboard',component},
    {path:'/graphs',name:'graphs',component},
    ...['','/window/:window','/window/:window/fork/:fork','/window/:window/fork/:fork/turn/:turn'].map((suffix,index)=>({path:`/run/:id${suffix}`,name:['run','window','fork','turn'][index],component,meta:{run:true}})),
    {path:'/files/:name(.*)',name:'file',component},
  ],
})
export const fileLink=(src,name,line)=>router.resolve({name:'file',params:{name},query:{src,...(line?{line:String(line)}:{})}}).href
export function resolveFile(url) {
  const route=router.resolve(new URL(url,location.href).hash.slice(1))
  return route.name==='file'?{name:route.params.name,...route.query}:null
}
