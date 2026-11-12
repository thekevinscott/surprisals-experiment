import test from 'node:test'
import assert from 'node:assert/strict'
import {sampleFiles,fileTree} from '../src/composables/sampleFiles.js'

test('T files retain every attempt and nested path without merging same-name files',()=>{
  const attempts=[{id:0,files:[{name:'main.py',source:'a/main.py'}]},{id:1,files:[{name:'main.py',source:'b/main.py'},{name:'lib/util.py',source:'b/lib/util.py'}]}]
  const files=sampleFiles(attempts,source=>'/raw/'+source)
  assert.deepEqual(files.map(file=>file.path),['Attempt 0/main.py','Attempt 1/main.py','Attempt 1/lib/util.py'])
  assert.deepEqual(files.map(file=>file.url),['/raw/a/main.py','/raw/b/main.py','/raw/b/lib/util.py'])
  const tree=fileTree(files)
  assert.equal(tree.length,2)
  assert.equal(tree[0].children[0].file,files[0])
  assert.equal(tree[1].children[1].children[0].file,files[2])
})

test('single attempt has no extra attempt layer, and empty attempts have no fake file',()=>{
  const files=sampleFiles([{id:4,files:[{name:'main.py',source:'a/main.py'}]}],source=>source)
  assert.equal(files[0].path,'main.py')
  assert.equal(fileTree(files)[0].file,files[0])
  assert.deepEqual(sampleFiles([{id:0,files:[]}],source=>source),[])
})
