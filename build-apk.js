const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

/**
 * 構建 Android Debug APK
 * - 自動尋找合適的 JDK（優先 Java 17，避開 Java 25 等 Gradle 不支援的版本）
 * - 執行 build-www、cap sync、gradlew assembleDebug
 */

function log(msg) {
  console.log(`[build-apk] ${msg}`);
}

function findJdk17() {
  const candidates = [];

  // 1. 檢查目前 JAVA_HOME 是否可用
  if (process.env.JAVA_HOME) {
    candidates.push(process.env.JAVA_HOME);
  }

  // 2. 常見的 .jdks 路徑
  const jdksDir = path.join(os.homedir(), '.jdks');
  if (fs.existsSync(jdksDir)) {
    fs.readdirSync(jdksDir)
      .filter(name => /^(ms|corretto|openjdk|temurin|zulu)-17/i.test(name))
      .forEach(name => candidates.push(path.join(jdksDir, name)));
  }

  // 3. Windows 常見安裝路徑
  const programFiles = [process.env['ProgramFiles'], process.env['ProgramFiles(x86)']];
  for (const pf of programFiles) {
    if (!pf) continue;
    const adoptiumDir = path.join(pf, 'Eclipse Adoptium');
    if (fs.existsSync(adoptiumDir)) {
      fs.readdirSync(adoptiumDir)
        .filter(name => /^jdk-17/i.test(name))
        .forEach(name => candidates.push(path.join(adoptiumDir, name)));
    }
  }

  for (const candidate of candidates) {
    const javaExe = path.join(candidate, 'bin', process.platform === 'win32' ? 'java.exe' : 'java');
    if (!fs.existsSync(javaExe)) continue;

    try {
      const output = execSync(`"${javaExe}" -version 2>&1`, { encoding: 'utf8' });
      const match = output.match(/version "(\d+)/);
      if (match) {
        const major = parseInt(match[1], 10);
        if (major === 17) {
          return candidate;
        }
      }
    } catch (e) {
      // ignore
    }
  }

  return null;
}

function run(cmd, options = {}) {
  log(`執行: ${cmd}`);
  execSync(cmd, { stdio: 'inherit', ...options });
}

function main() {
  const isWin = process.platform === 'win32';

  // 1. 構建 www
  run('node build-www.js');

  // 2. Capacitor sync
  run('npx cap sync android');

  // 3. 尋找 JDK 17
  const jdkPath = findJdk17();
  if (!jdkPath) {
    console.error('\n❌ 找不到 Java 17 JDK。');
    console.error('請安裝 Java 17 並設定 JAVA_HOME，或將其放在 %USERPROFILE%\\.jdks\\ms-17.0.19');
    process.exit(1);
  }
  log(`使用 JDK: ${jdkPath}`);

  // 4. 設定環境變數
  const env = { ...process.env };
  env.JAVA_HOME = jdkPath;
  const sep = isWin ? ';' : ':';
  env.PATH = path.join(jdkPath, 'bin') + sep + env.PATH;

  // 5. 執行 Gradle build
  const cwd = path.join(__dirname, 'android');
  const gradlew = path.join(cwd, isWin ? 'gradlew.bat' : 'gradlew');
  run(`"${gradlew}" assembleDebug`, {
    cwd,
    env,
    shell: true
  });

  const apkPath = path.join(__dirname, 'android', 'app', 'build', 'outputs', 'apk', 'debug', 'app-debug.apk');
  if (fs.existsSync(apkPath)) {
    log(`✅ APK 構建成功: ${apkPath}`);
  } else {
    log('⚠️ 未找到輸出的 APK，請檢查上面的 Gradle 輸出');
  }
}

main();
