const colors = ['#2563a6', '#d57920', '#29834b', '#9a4fa0', '#c54646', '#238d98']

export function createChartData(rows) {
const problems = [...new Set(rows.map(r => r.problem))]
const series = rows.map(row => {
  const advice = [], improvements = []
  for (const [depth, score] of row.passing ?? []) {
    if (!advice.length || score < advice.at(-1)[1]) {
      if (advice.length) improvements.push([depth, depth - advice.at(-1)[0]])
      advice.push([depth, score])
    }
  }
  return {
    strategy: row.strategy, problem: row.problem, cell: row.id,
    color: colors[problems.indexOf(row.problem) % colors.length],
    running: !row.ended, exit_code: row.exit, advice, improvements,
    passing: row.passing ?? [],
    scored: row.scored ?? [],
    streak: advice.length ? [[Math.max(0, row.turns - 1), Math.max(0, row.turns - 1 - advice.at(-1)[0])]] : [],
  }
})
const x = [0, Math.max(10, ...rows.map(r => r.turns)) + 2]
const domain = values => ({ x, y: [0, Math.max(1, ...values) * 1.05] })
return {
  arms: [...new Set(rows.map(r => r.strategy))], series,
  domains: {
    advice: domain(series.filter(s => s.strategy !== 'surprisal').flatMap(s => s.passing.map(p => p[1]))),
    surprisal: domain(series.filter(s => s.strategy === 'surprisal').flatMap(s => s.passing.map(p => p[1]))),
    improvements: domain(series.flatMap(s => [...s.improvements, ...s.streak].map(p => p[1]))),
  },
  wait: series.map(s => ({ ...s,
    bests: s.improvements.map(([depth, gap], i) => [depth, s.advice[i + 1][1], gap]),
    pending: s.advice.length ? [s.advice.at(-1)[1], s.streak[0][1]] : [0, 0],
  })),
}

}

// Each window starts new forks, so their identities include both window and fork.
export function createForkChartData(row) {
  const forks = row.forks ?? []
  const chart = createChartData(forks.map(fork => ({...row, ...fork, id:`${row.id}/windows/${fork.window}/forks/${fork.id}`})))
  chart.series.forEach((series, index) => {
    const fork = forks[index]
    series.label = `Window ${fork.window} · Fork ${fork.id}`
    series.color = index < colors.length ? colors[index] : `hsl(${Math.round(index * 137.508) % 360} 65% 40%)`
  })
  return chart
}

// The run graph keeps one line per fork through successive windows.
export function createRunChartData(row) {
  const forks = new Map()
  for (const fork of row.forks ?? []) {
    if (!forks.has(fork.id)) forks.set(fork.id, {...row, id:fork.id, passing:[], scored:[]})
    const series = forks.get(fork.id)
    series.passing.push(...fork.passing)
    series.scored.push(...fork.scored ?? [])
  }
  const rows = [...forks.values()].sort((a,b)=>a.id-b.id)
  for (const fork of rows) {
    fork.passing.sort((a,b)=>a[0]-b[0])
    fork.scored.sort((a,b)=>a[0]-b[0])
  }
  const chart = createChartData(rows)
  chart.series.forEach((series,index)=>{
    series.label = `Fork ${rows[index].id}`
    series.color = colors[index % colors.length]
  })
  for (const [key, surp] of [['advice',false],['surprisal',true]]) {
    chart.domains[key].y = [0, Math.max(1,...chart.series.filter(s=>(s.strategy==='surprisal')===surp).flatMap(s=>s.scored.map(p=>p[1]))) * 1.05]
  }
  return chart
}
