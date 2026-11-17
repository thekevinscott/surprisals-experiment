export function runStatus(run) {
  if (!run.ended && run.exit == null) return run.status
  if (run.exit === 0) return 'success'
  return [run.status, run.exit == null ? null : `exit ${run.exit}`, run.cause].filter(Boolean).join(' · ')
}

export const runCounts = rows => `${rows.filter(row => row.status === 'Complete').length} / ${rows.length} complete`
