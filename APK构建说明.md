# CatHealth Monitor APK 构建说明

## 前置要求

1. **Node.js** (v16 或更高)
   - 下载: https://nodejs.org/

2. **Java JDK** (v11 或更高)
   - 下载: https://adoptium.net/
   - 设置环境变量 JAVA_HOME

3. **Android Studio** (包含 Android SDK)
   - 下载: https://developer.android.com/studio
   - 设置环境变量 ANDROID_SDK_ROOT

4. **Gradle** (可选，Android Studio 自带)

## 快速构建步骤

### 方法一：使用批处理脚本（推荐）

```bash
双击运行 build-apk.bat
```

脚本会自动完成所有步骤。

### 方法二：手动步骤

1. **安装依赖**
   ```bash
   npm install
   ```

2. **添加 Android 平台**（首次）
   ```bash
   npx cap add android
   ```

3. **同步网页代码到 Android 项目**
   ```bash
   npx cap sync android
   ```

4. **构建 APK**
   ```bash
   cd android
   ./gradlew assembleRelease
   ```

5. **获取 APK**
   - 路径: `android/app/build/outputs/apk/release/app-release-unsigned.apk`

## 输出文件

构建完成后，APK 文件位于：
```
android/app/build/outputs/apk/release/app-release-unsigned.apk
```

## 签名发布（可选）

如需发布到应用商店，需要对 APK 进行签名：

```bash
cd android/app/build/outputs/apk/release

# 生成签名密钥（只需执行一次）
keytool -genkey -v -keystore cathealth.keystore -alias cathealth -keyalg RSA -keysize 2048 -validity 10000

# 签名 APK
jarsigner -verbose -sigalg SHA1withRSA -digestalg SHA1 -keystore cathealth.keystore app-release-unsigned.apk cathealth

# 优化 APK
zipalign -v 4 app-release-unsigned.apk CatHealthMonitor.apk
```

## 应用权限说明

本应用需要以下权限：

- **网络访问**: 连接后端服务器
- **相机**: 拍摄猫咪粪便照片进行分析
- **存储**: 保存和上传照片
- **位置**: 显示附近宠物医院地图

## 常见问题

### 1. Gradle 构建失败
确保 ANDROID_SDK_ROOT 环境变量正确设置。

### 2. 找不到 Android SDK
在 Android Studio 中打开 SDK Manager，安装 Android SDK Platform 33。

### 3. APK 安装失败
确保设备允许安装来自未知来源的应用。

## 技术支持

如遇到问题，请检查：
1. 所有环境变量是否正确设置
2. Node.js、Java、Android SDK 版本是否兼容
3. 网络连接是否正常（需要下载依赖）
