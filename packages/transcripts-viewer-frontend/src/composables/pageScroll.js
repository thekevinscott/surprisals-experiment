import {ref,nextTick} from 'vue'
import {until} from '@vueuse/core'

export const pageReady=ref(false)
export const pageRestoring=ref(false)
export async function scrollBehavior(to,from,savedPosition) {
  if(to.path===from.path)return false
  await until(pageReady).toBe(true)
  await nextTick()
  let offset=[0,0]
  try{offset=JSON.parse(to.query['scroll:page']??'[0,0]')}catch{}
  pageRestoring.value=false
  return savedPosition??{left:offset[0],top:offset[1]}
}
