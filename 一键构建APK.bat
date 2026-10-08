@echo off
chcp 65001
cls
echo ==========================================
echo   CatHealth Monitor 一键构建脚本
echo ==========================================
echo.
echo 本脚本将帮助你构建安卓 APK 文件
echo.

REM 检查 Node.js
node -v >nul 2>&1
if errorlevel 1 (
    echo [X] 未检测到 Node.js
    echo.
    echo 请先安装 Node.js:
    echo https://nodejs.org/dist/v18.17.1/node-v18.17.1-x64.msi
    echo.
    pause
    exit /b 1
)
echo [OK] Node.js 已安装

REM 检查 Java
java -version >nul 2>&1
if errorlevel 1 (
    echo [X] 未检测到 Java JDK
    echo.
    echo 请先安装 Java JDK 11:
    echo https://adoptium.net/temurin/releases/?version=11
    echo.
    pause
    exit /b 1
)
echo [OK] Java 已安装

REM 检查 Android SDK
if not defined ANDROID_SDK_ROOT (
    if not defined ANDROID_HOME (
        echo [X] 未设置 Android SDK 路径
        echo.
        echo 请先安装 Android Studio:
        echo https://developer.android.com/studio
        echo.
        echo 安装后设置环境变量:
        echo ANDROID_SDK_ROOT = C:\Users\你的用户名\AppData\Local\Android\Sdk
        echo.
        pause
        exit /b 1
    ) else (
        set ANDROID_SDK_ROOT=%ANDROID_HOME%
    )
)
echo [OK] Android SDK 已设置: %ANDROID_SDK_ROOT%

echo.
echo ==========================================
echo   开始构建
echo ==========================================
echo.

REM 步骤1: 安装依赖
echo [1/5] 安装 Node.js 依赖...
call npm install --no-fund --no-audit
if errorlevel 1 (
    echo [X] 安装依赖失败
    pause
    exit /b 1
)
echo [OK] 依赖安装完成

REM 步骤2: 初始化 Capacitor（如果不存在）
if not exist "android\" (
    echo [2/5] 初始化 Capacitor Android 项目...
    call npx cap add android
    if errorlevel 1 (
        echo [X] 添加 Android 平台失败
        pause
        exit /b 1
    )
) else (
    echo [2/5] Android 项目已存在，跳过初始化
)

REM 步骤3: 同步代码
echo [3/5] 同步网页代码到 Android 项目...
call npx cap sync android
if errorlevel 1 (
    echo [X] 同步失败
    pause
    exit /b 1
)
echo [OK] 同步完成

REM 步骤4: 复制资源文件
echo [4/5] 检查资源文件...
if not exist "android\app\src\main\res\mipmap-hdpi\ic_launcher.png" (
    echo [!] 警告: 未找到应用图标
    echo     将使用默认 Android 图标
    echo     如需自定义图标，请查看: 生成图标说明.md
)

REM 步骤5: 构建 APK
echo [5/5] 构建 APK 文件...
cd android

if not exist "gradlew.bat" (
    echo 正在生成 Gradle wrapper...
    call gradle wrapper
)

echo.
echo 正在构建，这可能需要几分钟...
echo.

call gradlew.bat assembleDebug --no-daemon

if errorlevel 1 (
    echo.
    echo [X] 构建失败
    cd ..
    pause
    exit /b 1
)

cd ..

echo.
echo ==========================================
echo   构建成功！
echo ==========================================
echo.
echo APK 文件位置:
echo   android\app\build\outputs\apk\debug\app-debug.apk
echo.
echo 安装到手机:
echo   1. 将上述 APK 文件复制到手机
    echo   2. 在手机上点击安装
    echo   3. 允许"安装未知来源应用"
echo.
echo 或者直接运行:
echo   npx cap run android
echo.

choice /C YN /M "是否立即安装到已连接的手机"
if errorlevel 2 exit /b 0
if errorlevel 1 (
    echo 正在安装...
    call npx cap run android
)

pause
