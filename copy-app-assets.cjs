const fs = require('fs')
const path = require('path')

const root = __dirname
const dist = path.join(root, 'dist')
const entries = [
  'auth.html',
  'dashboard.html',
  'auth.js',
  'hospital-map.js',
  'manifest.json',
  'service-worker.js',
  'images',
]

function copyEntry(entry) {
  const source = path.join(root, entry)
  const target = path.join(dist, entry)

  if (!fs.existsSync(source)) {
    throw new Error(`Missing application asset: ${entry}`)
  }

  fs.cpSync(source, target, { recursive: true })
  console.log(`Copied ${entry}`)
}

if (!fs.existsSync(dist)) {
  throw new Error('Missing dist directory. Run Vite before copying application assets.')
}

entries.forEach(copyEntry)
