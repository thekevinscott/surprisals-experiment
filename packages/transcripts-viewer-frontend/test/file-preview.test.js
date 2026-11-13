import test from 'node:test'
import assert from 'node:assert/strict'
import {filePreview,openFile,openFiles,selectPreviewFile,closeFile} from '../src/composables/filePreview.js'
import {sampleColumnCount} from '../src/composables/sampleFiles.js'

test('file modal has one raw link that follows selected file',()=>{
 const files=[{name:'a.py',source:'attempt0/a.py',url:'/raw/a'},{name:'b.py',source:'attempt1/b.py',url:'/raw/b'}]
 openFiles({name:'T0 files',files})
 assert.deepEqual(filePreview.value.rawFiles,[{url:'/raw/a',source:'attempt0/a.py'}])
 selectPreviewFile(files[1])
 assert.deepEqual(filePreview.value.rawFiles,[{url:'/raw/b',source:'attempt1/b.py'}])
 assert.deepEqual(filePreview.value.files,files)
 closeFile()
})

test('short file titles retain renderer filename and original source link',()=>{
 globalThis.location={href:'http://localhost/',hash:''}
 globalThis.history={replaceState:(_state,_title,hash)=>{location.hash=hash}}
 openFile('http://localhost/#files/windows%2F0%2Ftests.json?src=%2Fapi%2Ffiles%2Ftests.json')
 assert.equal(filePreview.value.title,'Test results')
 assert.equal(filePreview.value.name,'windows/0/tests.json')
 assert.deepEqual(filePreview.value.rawFiles,[{url:'/api/files/tests.json',source:'windows/0/tests.json'}])
 openFile('http://localhost/#files/advices%2Fhash%2Fadvice.txt?src=%2Fapi%2Ffiles%2Fadvice.txt')
 assert.equal(filePreview.value.title,'Advice')
 assert.ok(new URLSearchParams(location.hash.split('?')[1]).has('modal'))
 closeFile();assert.equal(location.hash,'#dashboard');delete globalThis.location;delete globalThis.history
})

test('in-progress samples reserve configured columns without hiding extra recorded samples',()=>{
 assert.equal(sampleColumnCount(5,3),5)
 assert.equal(sampleColumnCount(5,5),5)
 assert.equal(sampleColumnCount(2,3),3)
 assert.equal(sampleColumnCount(null,3),3)
})

test('transcript preview shows one selected source file, preserving physical line scope',async()=>{
 const {openTranscript}=await import('../src/composables/filePreview.js')
 const files=[{source:'attempt0/a.jsonl',url:'/a'},{source:'attempt1/b.jsonl',url:'/b'}]
 openTranscript({name:'T0 transcript',files},files[1])
 assert.deepEqual(filePreview.value.files,[files[1]])
 assert.equal(filePreview.value.source,'attempt1/b.jsonl')
 assert.deepEqual(filePreview.value.rawFiles,[files[1]])
 closeFile()
})

test('advice uses shared turn navigation, skips absent advice, and records source and turn in URL',async()=>{
 const {openAdvice,stepUTurn}=await import('../src/composables/filePreview.js')
 globalThis.location={href:'http://localhost/',hash:'#run/example'}
 globalThis.history={replaceState:(_state,_title,hash)=>{location.hash=hash}}
 try{
  const turns=[{id:0,advice:'first',adviceSource:'advices/a/advice.txt',tokens:[],measurement:2,unit:'bits'},
   {id:1,advice:null},{id:2,solo:true,advice:'last',adviceSource:'advices/b/advice.txt',tokens:[],measurement:1,unit:'bits'}]
  const sourceUrl=name=>`http://localhost/#files/${encodeURIComponent(name)}?src=${encodeURIComponent('/api/runs/example/files/'+name)}`
  openAdvice({sourceUrl,uNavigation:()=>({window:2,fork:2,turn:0,turns})})
  assert.equal(filePreview.value.title,'Window 2 · Fork 2 · Turn 0 · Advice')
  assert.deepEqual(filePreview.value.uNavigation().turns.map(t=>t.id),[0,2])
  stepUTurn(-1);assert.equal(filePreview.value.uTurnId,0)
  stepUTurn(1)
  assert.equal(filePreview.value.title,'Window 2 · Fork 2 continues · Turn 2 · Advice')
  assert.equal(filePreview.value.initialText,'last')
  assert.equal(filePreview.value.measurement,'1 bits')
  assert.equal(filePreview.value.rawFiles[0].source,'advices/b/advice.txt')
  const modal=JSON.parse(new URLSearchParams(location.hash.split('?')[1]).get('modal'))
  assert.equal(modal.kind,'advice');assert.deepEqual(modal.turn,{window:2,fork:2,id:2})
  assert.equal(modal.initialText,undefined)
  stepUTurn(1);assert.equal(filePreview.value.uTurnId,2)
  stepUTurn(-1);assert.equal(filePreview.value.initialText,'first')
  closeFile()
 }finally{delete globalThis.location;delete globalThis.history}
})
