import test from 'node:test'
import assert from 'node:assert/strict'
import {chartViewport} from '../src/composables/chartViewport.js'

test('resizing uses CSS pixels for the SVG viewport and changes only plot dimensions',()=>{
  for(const [width,height] of [[1280,180],[1280,400],[700,400]]){
    const view=chartViewport(width,height,true)
    assert.equal(view.width,width)
    assert.equal(view.height,height)
    assert.equal(width/view.width,1,'horizontal SVG unit remains one CSS pixel')
    assert.equal(height/view.height,1,'vertical SVG unit remains one CSS pixel')
    assert.equal(view.plotWidth,width-120)
    assert.equal(view.bottom,height-65)
  }
  assert.deepEqual(chartViewport(960,305,true),{width:960,height:305,plotWidth:840,bottom:240})
  assert.equal(chartViewport(960,285,false).bottom,240)
  assert.equal(chartViewport(960,40,true).bottom,31,'small panels keep a positive plot height')
})
