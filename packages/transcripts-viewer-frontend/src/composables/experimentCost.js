export function costTooltip(costs,pods,warnings=[]) {
  const money=value=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(value)
  const part=(label,key)=>`${label}: ${money(costs[key])}${costs.missing[key] ? ` (${costs.missing[key]} runs unavailable; excluded)` : ''}`
  return [part('U','u'),part('T','t'),part('AWS estimate (compute only)','aws'),
    `RunPod estimate (compute only): ${money(costs.runpod)}${pods.length ? '' : ' (no pod records; unrecorded costs excluded)'}`,
    'Total includes available recorded costs and estimated AWS/RunPod compute. EBS and data transfer excluded.',...warnings].join('\n')
}
