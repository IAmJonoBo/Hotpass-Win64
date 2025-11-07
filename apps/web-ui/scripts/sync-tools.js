#!/usr/bin/env node
import { copyFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import process from 'node:process'

const __dirname = dirname(fileURLToPath(import.meta.url))

// Skip if SKIP_TOOLS_SYNC environment variable is set (for Docker builds)
if (process.env.SKIP_TOOLS_SYNC === '1') {
  console.log('Skipping tools sync (SKIP_TOOLS_SYNC=1)')
  process.exit(0)
}

const repoRoot = resolve(__dirname, '..', '..', '..')
const publicDir = resolve(__dirname, '..', 'public')
const copies = [
  {
    source: resolve(repoRoot, 'tools.json'),
    dest: resolve(publicDir, 'tools.json'),
  },
  {
    source: resolve(repoRoot, 'docs', 'how-to-guides', 'e2e-walkthrough.md'),
    dest: resolve(publicDir, 'docs', 'e2e-walkthrough.md'),
  },
]

for (const { source, dest } of copies) {
  if (!existsSync(source)) {
    console.warn(`[sync-tools] skipping missing ${source}`)
    continue
  }
  mkdirSync(dirname(dest), { recursive: true })
  copyFileSync(source, dest)
}
