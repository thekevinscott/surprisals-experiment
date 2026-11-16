const colors = ['light-dark(#2563a6, #60a5fa)', 'light-dark(#d57920, #fb923c)', 'light-dark(#29834b, #4ade80)', 'light-dark(#9a4fa0, #d8b4fe)', 'light-dark(#c54646, #f87171)', 'light-dark(#238d98, #67e8f9)']
function decorate(chart) {
  return {...chart,series:chart.series.map(series=>({...series,color:colors[series.colorIndex]??`light-dark(hsl(${Math.round(series.colorIndex*137.508)%360} 65% 40%), hsl(${Math.round(series.colorIndex*137.508)%360} 65% 70%))`}))}
}
export const createRunChartData = row => decorate(row.charts.run)
export const createForkPhaseChartData = (row,window,id,solo=false) => decorate(row.charts[`${window}/${id}/${solo?'solo':'parallel'}`])
