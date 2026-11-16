# Viewer backend

Install with `pnpm install`. This builds dirsql's TypeScript SDK and native Rust
addon from the GitHub commit in `package.json` → `dirsqlSource.commit` (pinned
from `main`). Git, Rust/Cargo, Node, and pnpm are required. No PyPI or npm dirsql
release is used.

The source checkout and build output live in ignored `.dirsql-source/`;
`node_modules/dirsql` links to its `packages/ts` directory. To update the pin,
change the commit and run `pnpm install` again. Do not edit that checkout: the
install script checks out the pinned revision. Restart the viewer after an
update so its workers load the new native addon.

Run backend checks with `pnpm test`.
