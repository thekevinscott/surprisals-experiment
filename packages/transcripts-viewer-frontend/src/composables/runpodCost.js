export function runpodTooltip(pods) {
  return 'Estimated RunPod compute cost only.\n'+pods.map(pod=>`${pod.id} · ${pod.gpu} · $${pod.costPerHr}/hr\nStart: ${pod.start}\nStop: ${pod.stop??'live'}`).join('\n\n')
}
