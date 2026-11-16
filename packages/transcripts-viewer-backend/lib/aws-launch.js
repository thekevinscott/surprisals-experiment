export async function instanceLaunch(directory,database) {
  const [{launched}]=await database.query('SELECT min(launched) AS launched FROM launch_events')
  return launched
}
