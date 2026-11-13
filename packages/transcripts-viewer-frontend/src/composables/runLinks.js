import {router} from '../router.js'
export function runLink(id, source = '') {
  const suffix = source.replace(/^windows\//, 'window/').replace('/forks/', '/fork/').replace('/turns/', '/turn/')
  return router.resolve(`/run/${encodeURIComponent(id)}${suffix ? '/' + suffix : ''}`).href
}
