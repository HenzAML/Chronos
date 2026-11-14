import { execFileSync } from 'node:child_process'
import path from 'node:path'

export const API_PORT = 5002
export const WEB_PORT = 5174
export const DB_URL = process.env.E2E_DATABASE_URL
  ?? 'postgresql://chronos:chronos@localhost:5432/chronos_e2e'

export const BACKEND = path.resolve(import.meta.dirname, '..', '..', 'backend')
export const PY = path.join(BACKEND, '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')

export function py(...args: string[]) {
  execFileSync(PY, args, {
    cwd: BACKEND, stdio: 'pipe', env: { ...process.env, DATABASE_URL: DB_URL },
  })
}

/** Wipe the e2e database and load one seed profile. */
export const seed = (...flags: string[]) => py('scripts/seed.py', '--reset', ...flags)
