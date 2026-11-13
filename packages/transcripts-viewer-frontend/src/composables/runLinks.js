export function runLink(id, source = '') {
  const suffix = source.replace(/^windows\//, 'window/').replace('/forks/', '/fork/').replace('/turns/', '/turn/')
  return `#run/${encodeURIComponent(id)}${suffix ? '/' + suffix : ''}`
}
export function runRoute(hash) {
  const match=hash.split('?')[0].match(/^#run\/([^/]+)(?:\/window\/(\d+))?(?:\/fork\/(\d+))?(?:\/turn\/(\d+))?$/)
  return match ? {id:decodeURIComponent(match[1]),window:match[2],fork:match[3],turn:match[4]} : null
}
