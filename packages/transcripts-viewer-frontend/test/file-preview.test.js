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
 globalThis.location={href:'http://localhost/'}
 openFile('http://localhost/#files/windows%2F0%2Ftests.json?src=%2Fapi%2Ffiles%2Ftests.json')
 assert.equal(filePreview.value.title,'Test results')
 assert.equal(filePreview.value.name,'windows/0/tests.json')
 assert.deepEqual(filePreview.value.rawFiles,[{url:'/api/files/tests.json',source:'windows/0/tests.json'}])
 openFile('http://localhost/#files/advices%2Fhash%2Fadvice.txt?src=%2Fapi%2Ffiles%2Fadvice.txt')
 assert.equal(filePreview.value.title,'Advice')
 closeFile();delete globalThis.location
})

test('in-progress samples reserve configured columns without hiding extra recorded samples',()=>{
 assert.equal(sampleColumnCount(5,3),5)
 assert.equal(sampleColumnCount(5,5),5)
 assert.equal(sampleColumnCount(2,3),3)
 assert.equal(sampleColumnCount(null,3),3)
})
