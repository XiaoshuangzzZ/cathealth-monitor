const fs = require('fs');
const path = require('path');

/**
 * 將頂層前端檔案複製到 www/，供 Capacitor 打包 Android APK 使用
 * 用法：node build-www.js
 */

const filesToCopy = [
  'index.html',
  'dashboard.html',
  'auth.js',
  'hospital-map.js',
  'manifest.json',
  'service-worker.js'
];

const dirsToCopy = [
  'images/icons'
];

const wwwDir = path.join(__dirname, 'www');

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
    console.log(`Created: ${dir}`);
  }
}

function copyFile(src, dest) {
  fs.copyFileSync(src, dest);
  console.log(`Copied: ${src} -> ${dest}`);
}

function copyDir(src, dest) {
  ensureDir(dest);
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      copyFile(srcPath, destPath);
    }
  }
}

// 清空並重建 www
if (fs.existsSync(wwwDir)) {
  fs.rmSync(wwwDir, { recursive: true, force: true });
  console.log('Cleaned: www/');
}
ensureDir(wwwDir);

for (const file of filesToCopy) {
  const src = path.join(__dirname, file);
  const dest = path.join(wwwDir, file);
  if (!fs.existsSync(src)) {
    console.warn(`Missing source file: ${src}`);
    continue;
  }
  copyFile(src, dest);
}

for (const dir of dirsToCopy) {
  const src = path.join(__dirname, dir);
  const dest = path.join(wwwDir, dir);
  if (!fs.existsSync(src)) {
    console.warn(`Missing source directory: ${src}`);
    continue;
  }
  copyDir(src, dest);
}

console.log('\n✅ www/ 构建完成');
console.log('下一步请执行: npx cap sync android');
console.log('然后进入 android 目录运行: ./gradlew assembleDebug');
