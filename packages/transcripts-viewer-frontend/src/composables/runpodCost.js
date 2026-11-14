export function runpodCost(pods,now) {
  return pods.reduce((sum,pod)=>sum+Math.max(0,(pod.stop?Date.parse(pod.stop):now)-Date.parse(pod.start))/3600000*pod.costPerHr,0)
}
export function runpodTooltip(pods) {
  return 'Estimated RunPod compute cost only.\n'+pods.map(pod=>`${pod.id} · ${pod.gpu} · $${pod.costPerHr}/hr\nStart: ${pod.start}\nStop: ${pod.stop??'live'}`).join('\n\n')
}
