const colors = ['light-dark(#2563a6, #60a5fa)', 'light-dark(#d57920, #fb923c)', 'light-dark(#29834b, #4ade80)', 'light-dark(#9a4fa0, #d8b4fe)', 'light-dark(#c54646, #f87171)', 'light-dark(#238d98, #67e8f9)']

export function createChartData(rows) {
const problems = [...new Set(rows.map(r => r.problem))]
const series = rows.map(row => {
  const advice = []
  for (const [depth, score] of row.passing ?? []) {
    if (!advice.length || score < advice.at(-1)[1]) {
      advice.push([depth, score])
    }
  }
  return {
    strategy: row.strategy, problem: row.problem, cell: row.id,
    color: colors[problems.indexOf(row.problem) % colors.length],
    running: !row.ended, exit_code: row.exit, advice,
    passing: row.passing ?? [],
    scored: row.scored ?? [],
  }
})
const x = [0, Math.max(10, ...rows.map(r => r.turns)) + 2]
const domain = values => ({ x, y: [0, Math.max(1, ...values) * 1.05] })
return {
  arms: [...new Set(rows.map(r => r.strategy))], series,
  domains: {
    advice: domain(series.filter(s => s.strategy !== 'surprisal').flatMap(s => s.passing.map(p => p[1]))),
    surprisal: domain(series.filter(s => s.strategy === 'surprisal').flatMap(s => s.passing.map(p => p[1]))),
  },

}

}

// Each window starts new forks, so their identities include both window and fork.
export function createForkChartData(row) {
  const forks = row.forks ?? []
  const chart = createChartData(forks.map(fork => ({...row, ...fork, id:`${row.id}/windows/${fork.window}/forks/${fork.id}`})))
  chart.series.forEach((series, index) => {
    const fork = forks[index]
    series.turnStart = fork.window * (row.forkTurns + row.soloTurns)
    series.window = fork.window
    series.fork = fork.id
    series.continues = fork.turns > fork.window * (row.forkTurns + row.soloTurns) + row.forkTurns
    series.label = `Window ${fork.window} · Fork ${fork.id}`
    series.color = index < colors.length ? colors[index] : `light-dark(hsl(${Math.round(index * 137.508) % 360} 65% 40%), hsl(${Math.round(index * 137.508) % 360} 65% 70%))`
  })
  return chart
}

// Fork IDs are local to each window; lines contain only that fork’s turns.
export function createRunChartData(row) {
  const chart = createForkChartData(row)
  chart.windowPositions = row.windowPositions ?? []
  chart.series.forEach(series=>{
    series.scored = [...series.scored].sort((a,b)=>a[0]-b[0])
  })
  for (const [key, surp] of [['advice',false],['surprisal',true]]) {
    chart.domains[key].y = [0, Math.max(1,...chart.series.filter(s=>(s.strategy==='surprisal')===surp).flatMap(s=>s.scored.map(p=>p[1]))) * 1.05]
  }
  return chart
}

export function createForkPhaseChartData(row, window, id, solo=false) {
  const start = window * (row.forkTurns + row.soloTurns) + (solo ? row.forkTurns : 0)
  const end = start + (solo ? row.soloTurns : row.forkTurns)
  const all = createRunChartData(row)
  const forks = (row.forks ?? []).filter(f=>f.window===window && f.id===id).map(f=>({...f,
    passing:f.passing.filter(([depth])=>depth>=start && depth<end),
    scored:(f.scored ?? []).filter(([depth])=>depth>=start && depth<end)}))
  const chart = createForkChartData({...row,forks})
  for (const kind of ['advice','surprisal']) chart.domains[kind] = {x:[start,end],y:all.domains[kind].y}
  return chart
}
