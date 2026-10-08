const fs = require('fs')
const path = require('path')

/**
 * 将已构建的动态介绍页与既有 CatHealth 静态页面复制到 www/，供 Capacitor 打包 Android APK 使用。
 * 使用方式：npm run build:www
 */
const root = __dirname
const sourceDir = path.join(root, 'dist')
const targetDir = path.join(root, 'www')

if (!fs.existsSync(path.join(sourceDir, 'index.html'))) {
  throw new Error('缺少 dist/index.html，请先运行 npm run build。')
}

if (fs.existsSync(targetDir)) {
  fs.rmSync(targetDir, { recursive: true, force: true })
  console.log('Cleaned: www/')
}

fs.cpSync(sourceDir, targetDir, { recursive: true })
console.log('Copied built landing page and CatHealth static assets to www/')
console.log('下一步请执行: npx cap sync android')
console.log('然后进入 android 目录运行: ./gradlew assembleDebug')
