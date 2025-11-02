#!/usr/bin/env node
import { copyFileSync, mkdirSync } from 'node:fs'
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
const source = resolve(repoRoot, 'tools.json')
const destDir = resolve(__dirname, '..', 'public')
const dest = resolve(destDir, 'tools.json')

mkdirSync(destDir, { recursive: true })
copyFileSync(source, dest)
