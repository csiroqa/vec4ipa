#!/usr/bin/env node
/*
 * House-style limit checker.
 *
 * Usage:
 *   node check-limits.mjs --commit <msg-file>
 *   node check-limits.mjs --changed
 *   node check-limits.mjs --all
 *   node check-limits.mjs --limits <file> [--changed|--all|file...]
 *
 * Limits are read from --limits, then ./limits.yaml, then the global
 * limits.default.yaml beside this script's parent directory.
 */

import { existsSync, readFileSync, readdirSync } from "node:fs"
import { execFileSync } from "node:child_process"
import { dirname, join, relative, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const HERE = dirname(fileURLToPath(import.meta.url))
const DEFAULTS_FILE = join(HERE, "..", "limits.default.yaml")

const DEFAULTS = {
  git: {
    subject: { target: 50, hard: 72, unit: "chars" },
    body_line: { hard: 72, unit: "chars" },
    body_total: { target: 400, hard: 1000, unit: "auto" },
    require_signoff: false,
    allow_change_id: false,
  },
  docs: {
    sentence: { target: 20, hard: 25, unit: "auto" },
    paragraph: { target: 4, hard: 6, unit: "sentences" },
    heading: { target: 50, hard: 60, unit: "chars" },
    page: { target: 1200, hard: 2000, unit: "auto" },
  },
  openspec: {
    proposal: { target: 400, hard: 500, unit: "auto" },
    requirement: { target: 400, hard: 500, unit: "chars" },
    design: { target: 1000, hard: 1500, unit: "auto" },
    task: { target: 100, hard: 120, unit: "chars" },
  },
}

function parseArgs(argv) {
  const opts = { mode: "changed", commit: null, limits: null, files: [] }
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    if (arg === "--commit") opts.commit = argv[++i]
    else if (arg === "--changed") opts.mode = "changed"
    else if (arg === "--all") opts.mode = "all"
    else if (arg === "--limits") opts.limits = argv[++i]
    else if (arg === "--help" || arg === "-h") {
      printHelp()
      process.exit(0)
    } else if (arg.startsWith("-")) {
      console.error(`unknown option: ${arg}`)
      process.exit(2)
    } else {
      opts.files.push(arg)
    }
  }
  return opts
}

function printHelp() {
  console.log(`House-style limit checker

Usage:
  node check-limits.mjs --commit <msg-file>   Check a Git commit message
  node check-limits.mjs --changed             Check changed Markdown/OpenSpec files
  node check-limits.mjs --all                 Check all tracked Markdown/OpenSpec files
  node check-limits.mjs --limits <file> ...   Use a specific limits file
  node check-limits.mjs <file> ...            Check specific files

Limits file search: --limits, ./limits.yaml, ../limits.default.yaml.
Missing limits fall back to built-in defaults.`)
}

const opts = parseArgs(process.argv.slice(2))

function merge(base, extra) {
  const out = { ...base }
  for (const [key, value] of Object.entries(extra || {})) {
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      out[key] &&
      typeof out[key] === "object" &&
      !Array.isArray(out[key])
    ) {
      out[key] = merge(out[key], value)
    } else {
      out[key] = value
    }
  }
  return out
}

function splitTopLevel(text, separator) {
  const parts = []
  let depth = 0
  let quote = null
  let start = 0
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (quote) {
      if (ch === quote) quote = null
      continue
    }
    if (ch === '"' || ch === "'") {
      quote = ch
      continue
    }
    if (ch === "{") depth++
    else if (ch === "}") depth--
    else if (ch === separator && depth === 0) {
      parts.push(text.slice(start, i))
      start = i + 1
    }
  }
  parts.push(text.slice(start))
  return parts.map((part) => part.trim()).filter(Boolean)
}

function parseScalar(text) {
  const value = text.trim()
  if (value === "") return true
  if (value === "true") return true
  if (value === "false") return false
  if (value === "null" || value === "~") return null

  const object = value.match(/^\{(.*)\}$/)
  if (object) {
    const result = {}
    for (const part of splitTopLevel(object[1], ",")) {
      const index = part.indexOf(":")
      if (index < 0) continue
      result[part.slice(0, index).trim()] = parseScalar(part.slice(index + 1))
    }
    return result
  }

  const number = Number(value)
  if (value !== "" && !Number.isNaN(number)) return number
  return value.replace(/^["']|["']$/g, "")
}

function parseSimpleYaml(text) {
  const result = {}
  let section = null
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.replace(/\s+#.*$/, "")
    if (!line.trim() || line.trim().startsWith("#")) continue

    const top = line.match(/^([A-Za-z0-9_-]+):\s*$/)
    if (top) {
      section = top[1]
      result[section] = {}
      continue
    }

    const nested = line.match(/^\s+([A-Za-z0-9_-]+):\s*(.*)$/)
    if (nested && section) {
      result[section][nested[1]] = parseScalar(nested[2])
      continue
    }

    throw new Error(`unsupported YAML line: ${raw}`)
  }
  return result
}

function loadLimits() {
  const candidates = [
    opts.limits ? resolve(opts.limits) : null,
    join(process.cwd(), "limits.yaml"),
    DEFAULTS_FILE,
  ].filter(Boolean)

  for (const file of candidates) {
    if (!existsSync(file)) continue
    try {
      return merge(DEFAULTS, parseSimpleYaml(readFileSync(file, "utf8")))
    } catch (error) {
      console.error(`limits: cannot parse ${file}: ${error.message}; using defaults`)
    }
  }
  return DEFAULTS
}

const CJK_RE = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/gu
const LATIN_RE = /[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*/g
let sentenceSegmenter

function segmentSentences(text) {
  const value = String(text || "").trim()
  if (!value) return []
  const cjk = (value.match(CJK_RE) || []).length
  const latin = (value.match(LATIN_RE) || []).length
  if (cjk > latin) {
    return value.split(/(?<=[。！？!?])/).map((part) => part.trim()).filter(Boolean)
  }
  try {
    sentenceSegmenter ??= new Intl.Segmenter("en", { granularity: "sentence" })
    return [...sentenceSegmenter.segment(value)]
      .map((part) => part.segment.trim())
      .filter(Boolean)
  } catch {
    return value.split(/(?<=[.!?。！？])\s+/).map((part) => part.trim()).filter(Boolean)
  }
}

function countUnits(text, unit) {
  const value = String(text || "")
  if (unit === "chars") return Array.from(value).length
  if (unit === "sentences") return segmentSentences(value).length

  const cjk = (value.match(CJK_RE) || []).length
  const latin = (value.match(LATIN_RE) || []).length
  if (unit === "words") return latin || cjk
  return cjk + latin
}

function stripFrontmatter(text) {
  return String(text || "").replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, "")
}

function stripCode(text) {
  return String(text || "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/~~~[\s\S]*?~~~/g, "")
    .replace(/`[^`\r\n]*`/g, "")
}

function stripMarkdown(text) {
  return stripCode(stripFrontmatter(text))
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/https?:\/\/\S+/g, "URL")
    .replace(/<[^>]+>/g, "")
}

function getParagraphs(text) {
  const body = stripMarkdown(text)
  const blocks = body.split(/\r?\n\s*\r?\n/)
  const paragraphs = []
  let line = 1
  for (const block of blocks) {
    const rawLines = block.split(/\r?\n/)
    const trimmed = block.trim()
    if (!trimmed) {
      line += rawLines.length
      continue
    }
    const proseLines = rawLines.filter(
      (item) => !/^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s|\||>|<!--|!\[|---+$)/.test(item),
    )
    if (proseLines.length) paragraphs.push({ text: proseLines.join(" "), line })
    line += rawLines.length
  }
  return paragraphs
}

function addFinding(findings, severity, file, line, message) {
  findings.push({ severity, file, line, message })
}

function checkLimit(findings, file, line, label, value, rule) {
  if (!rule || typeof rule !== "object" || Number.isNaN(value)) return
  if (typeof rule.hard === "number" && value > rule.hard) {
    addFinding(findings, "error", file, line, `${label} ${value} > hard ${rule.hard}`)
  } else if (typeof rule.target === "number" && value > rule.target) {
    addFinding(findings, "warning", file, line, `${label} ${value} > target ${rule.target}`)
  }
}

function checkMarkdown(file, text, limits, findings) {
  checkLimit(findings, file, 1, "page", countUnits(stripMarkdown(text), limits.docs.page.unit), limits.docs.page)

  const visible = stripCode(stripFrontmatter(text))
  visible.split(/\r?\n/).forEach((line, index) => {
    const heading = line.match(/^(#{1,6})\s+(.*)$/)
    if (heading) {
      checkLimit(findings, file, index + 1, "heading", countUnits(heading[2], limits.docs.heading.unit), limits.docs.heading)
    }
  })

  for (const paragraph of getParagraphs(text)) {
    const sentences = segmentSentences(paragraph.text)
    checkLimit(findings, file, paragraph.line, "paragraph", sentences.length, limits.docs.paragraph)
    for (const sentence of sentences) {
      checkLimit(findings, file, paragraph.line, "sentence", countUnits(sentence, limits.docs.sentence.unit), limits.docs.sentence)
    }
  }
}

function checkCommit(file, limits, findings) {
  const lines = readFileSync(file, "utf8").replace(/\r\n/g, "\n").split("\n")
  const subject = lines[0] ?? ""
  const merge = /^Merge\b/.test(subject)

  if (!merge) {
    checkLimit(findings, file, 1, "subject", countUnits(subject, limits.git.subject.unit), limits.git.subject)
    if (/\.\s*$/.test(subject)) addFinding(findings, "error", file, 1, "subject must not end with a period")
    if (/^(WIP|fixup!|squash!)\b/i.test(subject)) {
      addFinding(findings, "error", file, 1, "subject contains a work-in-progress marker")
    }
  }

  if (lines.length > 1 && lines[1].trim() !== "") {
    addFinding(findings, "error", file, 2, "second line must be blank")
  }

  const trailer = /^(Signed-off-by|Reviewed-by|Tested-by|Acked-by|Reported-by|Suggested-by|Co-developed-by|Fixes|Cc|Link|Closes|Change-Id):/i
  const body = []
  for (let index = 2; index < lines.length; index++) {
    const line = lines[index]
    if (/^Fixes:/i.test(line) && !/^Fixes:\s+[0-9a-f]{12,40}\s+\(".*"\)/.test(line)) {
      addFinding(findings, "warning", file, index + 1, "Fixes: must use a 12+ character SHA and the quoted subject")
    }
    if (/^Signed-off-by:/i.test(line) && !/^Signed-off-by:\s+.+<[^>]+>/.test(line)) {
      addFinding(findings, "warning", file, index + 1, "Signed-off-by must include a name and email")
    }
    if (trailer.test(line)) continue
    body.push(line)
    const length = Array.from(line).length
    if (typeof limits.git.body_line.hard === "number" && length > limits.git.body_line.hard) {
      addFinding(findings, "error", file, index + 1, `body line ${length} > hard ${limits.git.body_line.hard}`)
    }
  }
  checkLimit(findings, file, 3, "body", countUnits(body.join(" "), limits.git.body_total.unit), limits.git.body_total)

  const hasSignoff = lines.some((line) => /^Signed-off-by:\s+.+<[^>]+>/.test(line))
  if (limits.git.require_signoff === true && !hasSignoff) {
    addFinding(findings, "error", file, 1, "missing Signed-off-by")
  }
  if (limits.git.allow_change_id !== true && lines.some((line) => /^Change-Id:/i.test(line))) {
    addFinding(findings, "error", file, 1, "Change-Id is not allowed")
  }
}

function checkRequirement(file, lines, start, end, title, limits, findings) {
  const body = lines.slice(start + 1, end).join("\n")
  const value = countUnits(body, limits.openspec.requirement.unit)
  checkLimit(findings, file, start + 1, "requirement", value, limits.openspec.requirement)
  if (!/\b(SHALL|MUST)\b/.test(body)) {
    addFinding(findings, "warning", file, start + 1, `requirement "${title}" lacks SHALL/MUST`)
  }
}

function checkOpenSpec(file, text, limits, findings) {
  const normalized = file.replace(/\\/g, "/")

  if (/\/proposal\.md$/.test(normalized)) {
    checkLimit(findings, file, 1, "proposal", countUnits(stripMarkdown(text), limits.openspec.proposal.unit), limits.openspec.proposal)
  } else if (/\/design\.md$/.test(normalized)) {
    checkLimit(findings, file, 1, "design", countUnits(stripMarkdown(text), limits.openspec.design.unit), limits.openspec.design)
  } else if (/\/tasks\.md$/.test(normalized)) {
    text.split(/\r?\n/).forEach((line, index) => {
      const task = line.match(/^\s*-\s*\[[ xX]\]\s+(.*)$/)
      if (task) checkLimit(findings, file, index + 1, "task", countUnits(task[1], limits.openspec.task.unit), limits.openspec.task)
    })
  }

  if (/\/specs\/.*\.md$/.test(normalized)) {
    const lines = text.split(/\r?\n/)
    let start = -1
    let title = ""
    for (let index = 0; index < lines.length; index++) {
      const match = lines[index].match(/^###\s+Requirement:\s*(.+)$/)
      if (match) {
        if (start >= 0) checkRequirement(file, lines, start, index, title, limits, findings)
        start = index
        title = match[1]
      }
    }
    if (start >= 0) checkRequirement(file, lines, start, lines.length, title, limits, findings)
  }
}

function runGit(args) {
  return execFileSync("git", args, {
    encoding: "utf8",
    cwd: process.cwd(),
    stdio: ["ignore", "pipe", "ignore"],
  })
}

function getChangedFiles() {
  const files = new Set()
  const commands = [
    ["diff", "--name-only", "--cached"],
    ["diff", "--name-only"],
    ["ls-files", "--others", "--exclude-standard"],
  ]
  for (const args of commands) {
    try {
      for (const file of runGit(args).split(/\r?\n/)) {
        if (file.trim()) files.add(file)
      }
    } catch {
      // Not a Git repository or Git is unavailable; fall through.
    }
  }
  return [...files]
}

function getAllFiles() {
  try {
    return runGit(["ls-files", "--cached", "--others", "--exclude-standard"]).split(/\r?\n/).filter(Boolean)
  } catch {
    const files = []
    const skip = new Set([".git", "node_modules", "dist", "build", "target", ".next", "vendor"])
    const walk = (dir, depth) => {
      if (depth > 4) return
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        if (skip.has(entry.name)) continue
        const full = join(dir, entry.name)
        if (entry.isDirectory()) walk(full, depth + 1)
        else files.push(relative(process.cwd(), full))
      }
    }
    walk(process.cwd(), 0)
    return files
  }
}

const IGNORED_DIRS = /^(?:\.opencode|\.claude|\.agents|\.cursor|\.github|\.git|node_modules|dist|build|target|vendor)\//i

function isTarget(file) {
  const normalized = file.replace(/\\/g, "/")
  if (IGNORED_DIRS.test(normalized)) return false
  return /\.mdx?$/i.test(normalized)
}

function main() {
  const limits = loadLimits()
  const findings = []

  if (opts.commit) {
    if (!existsSync(opts.commit)) {
      console.error(`commit message not found: ${opts.commit}`)
      process.exit(2)
    }
    checkCommit(opts.commit, limits, findings)
  } else {
    const files = opts.files.length ? opts.files : opts.mode === "all" ? getAllFiles() : getChangedFiles()
    for (const file of files.filter(isTarget)) {
      if (!existsSync(file)) continue
      const text = readFileSync(file, "utf8")
      if (file.replace(/\\/g, "/").startsWith("openspec/")) checkOpenSpec(file, text, limits, findings)
      else checkMarkdown(file, text, limits, findings)
    }
  }

  findings.sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line)
  for (const finding of findings) {
    console.log(`${finding.file}:${finding.line}: ${finding.severity}: ${finding.message}`)
  }

  const errors = findings.filter((finding) => finding.severity === "error").length
  const warnings = findings.length - errors
  if (!findings.length) console.log("limits: ok")
  else console.log(`\n${errors} error(s), ${warnings} warning(s)`)
  process.exit(errors ? 1 : 0)
}

main()
