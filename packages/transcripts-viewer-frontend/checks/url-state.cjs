const {chromium}=require('playwright')
const assert=require('node:assert/strict')
;(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH})
 const base=process.env.VIEWER_URL||'http://localhost:5173'
 const context=await browser.newContext({viewport:{width:1440,height:1000}})
 const page=await context.newPage()
 async function reloadAndCopy(check){
  const url=page.url();await page.reload();await check(page)
  const fresh=await browser.newContext({viewport:{width:1440,height:1000}}),tab=await fresh.newPage()
  try{await tab.goto(url);await check(tab)}finally{await fresh.close()}
 }
 try{
  await page.goto(`${base}/#run/20261113-034702-wild-recipe`)
  await page.getByRole('button',{name:'Collapse Graphs',exact:true}).click()
  await reloadAndCopy(p=>p.getByRole('button',{name:'Expand Graphs',exact:true}).waitFor())
  await page.getByRole('button',{name:'Expand Graphs',exact:true}).click()
  assert.ok(!new URLSearchParams(new URL(page.url()).hash.split('?')[1]).has('panel:/graphs'))
  await page.getByRole('button',{name:'Collapse Window 0',exact:true}).click()
  await reloadAndCopy(p=>p.getByRole('button',{name:'Expand Window 0',exact:true}).waitFor())
  console.log('Panels restore after reload/fresh tab; defaults omitted. Dashboard has no panels.')
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1})
