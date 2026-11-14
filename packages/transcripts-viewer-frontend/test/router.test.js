import test from 'node:test'
import assert from 'node:assert/strict'
import {router} from '../src/router.js'
test('viewer routes resolve dashboard, graphs, all drilldown levels and encoded file names',()=>{
 for(const [path,name] of [['/dashboard','dashboard'],['/graphs','graphs'],['/run/run-1','run'],['/run/run-1/window/2','window'],['/run/run-1/window/2/fork/3','fork'],['/run/run-1/window/2/fork/3/turn/4','turn']])assert.equal(router.resolve(path).name,name)
 assert.deepEqual(router.resolve('/run/run-1/window/2/fork/3/turn/4').params,{id:'run-1',window:'2',fork:'3',turn:'4'})
 const file=router.resolve({name:'file',params:{name:'folder/a b.jsonl'},query:{src:'/api/file',line:'49'}})
 assert.equal(router.resolve(file.fullPath).params.name,'folder/a b.jsonl')
 assert.equal(file.query.line,'49')
})
