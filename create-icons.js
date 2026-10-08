// 简单的图标生成脚本
// 运行: node create-icons.js

const fs = require('fs');
const path = require('path');

const sizes = {
  'mipmap-mdpi': 48,
  'mipmap-hdpi': 72,
  'mipmap-xhdpi': 96,
  'mipmap-xxhdpi': 144,
  'mipmap-xxxhdpi': 192
};

const baseDir = path.join(__dirname, 'android', 'app', 'src', 'main', 'res');

// 创建目录结构
Object.keys(sizes).forEach(dir => {
  const dirPath = path.join(baseDir, dir);
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
    console.log(`Created: ${dirPath}`);
  }
});

// 创建占位说明文件
const readme = path.join(baseDir, 'README.txt');
fs.writeFileSync(readme, `
请将生成的图标文件放入对应的文件夹：

每个 mipmap 文件夹需要以下文件：
- ic_launcher.png (主图标)
- ic_launcher_round.png (圆形图标)
- ic_launcher_foreground.png (前景)

建议使用 Android Asset Studio 生成：
https://romannurik.github.io/AndroidAssetStudio/icons-launcher.html
`);

console.log('\n✅ 图标目录结构已创建！');
console.log('\n请按以下步骤操作：');
console.log('1. 准备一张 512x512 的猫咪图片');
console.log('2. 访问 https://romannurik.github.io/AndroidAssetStudio/icons-launcher.html');
console.log('3. 上传图片并下载');
console.log('4. 将生成的文件复制到 android/app/src/main/res/ 对应目录');
