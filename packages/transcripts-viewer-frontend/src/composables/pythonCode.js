import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'

hljs.registerLanguage('python',python)
export const highlightPython = text => hljs.highlight(text,{language:'python'}).value
