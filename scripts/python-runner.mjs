import { existsSync } from "node:fs"
import { spawnSync } from "node:child_process"
import { resolve } from "node:path"

const windowsPython = resolve(process.cwd(), ".venv", "Scripts", "python.exe")
const posixPython = resolve(process.cwd(), ".venv", "bin", "python")
const python = existsSync(windowsPython)
  ? windowsPython
  : existsSync(posixPython)
    ? posixPython
    : "python"

const result = spawnSync(python, process.argv.slice(2), {
  cwd: process.cwd(),
  shell: false,
  stdio: "inherit",
})

if (result.error) {
  console.error(result.error.message)
  process.exit(1)
}

process.exit(result.status ?? 0)
