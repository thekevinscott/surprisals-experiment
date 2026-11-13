import test from 'node:test'
import assert from 'node:assert/strict'
import {highlightPython} from '../src/composables/pythonCode.js'

test('Python highlighting marks syntax and escapes HTML without executing source text',()=>{
  const html=highlightPython('def solve():\n    print("<script>alert(1)</script>")\n')
  assert.match(html,/class="hljs-keyword">def</)
  assert.match(html,/class="hljs-string"/)
  assert.ok(html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'))
  assert.ok(!html.includes('<script>'))
})
