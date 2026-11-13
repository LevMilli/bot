// Load a few pure src/data modules in plain Node for the look-rule tests.
// Uses Vite's own TypeScript transform, so no extra test dependency.
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { transformWithOxc } from 'vite'

const here = dirname(fileURLToPath(import.meta.url))
const dataDir = resolve(here, '..', 'src', 'data')

export async function loadData(names) {
  const out = mkdtempSync(join(tmpdir(), 'city-rules-'))
  for (const name of names) {
    const src = readFileSync(join(dataDir, `${name}.ts`), 'utf8')
    const { code } = await transformWithOxc(src, `${name}.ts`, { lang: 'ts' })
    writeFileSync(join(out, `${name}.mjs`), code.replace(/from (['"])\.\/([A-Za-z]+)\1/g, "from './$2.mjs'"))
  }
  const mods = {}
  for (const name of names) mods[name] = await import(pathToFileURL(join(out, `${name}.mjs`)).href)
  return mods
}
