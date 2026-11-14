import {awsCost} from './awsCost.js'
import {runpodCost} from './runpodCost.js'

export function experimentCost(rows,pods,now) {
  const costs={u:0,t:0,aws:0,runpod:runpodCost(pods,now),missing:{u:0,t:0,aws:0}}
  for(const row of rows) {
    for(const [key,value] of [['u',row.uCost],['t',row.tCost],['aws',awsCost(row,now)]]) {
      if(value==null)costs.missing[key]++
      else costs[key]+=value
    }
  }
  return {...costs,total:costs.u+costs.t+costs.aws+costs.runpod}
}
export function costTooltip(costs,pods,warnings=[]) {
  const money=value=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(value)
  const part=(label,key)=>`${label}: ${money(costs[key])}${costs.missing[key] ? ` (${costs.missing[key]} runs unavailable; excluded)` : ''}`
  return [part('U','u'),part('T','t'),part('AWS estimate (compute only)','aws'),
    `RunPod estimate (compute only): ${money(costs.runpod)}${pods.length ? '' : ' (no pod records; unrecorded costs excluded)'}`,
    'Total includes available recorded costs and estimated AWS/RunPod compute. EBS and data transfer excluded.',...warnings].join('\n')
}
