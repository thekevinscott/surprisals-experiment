export function createChartData(rows) {

const colors = ['#2563a6', '#d57920', '#29834b', '#9a4fa0', '#c54646', '#238d98']
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
