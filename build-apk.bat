@echo off
chcp 65001
cls
echo ==========================================
echo   CatHealth Monitor APK 构建脚本
echo ==========================================
echo.

REM 检查 Node.js
node -v >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Node.js，请先安装 Node.js
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)

echo [1/6] 检查 Node.js... OK

REM 检查 Java
java -version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Java JDK，请先安装 Java JDK 11 或更高版本
    echo 下载地址: https://adoptium.net/
    pause
    exit /b 1
)

echo [2/6] 检查 Java... OK

REM 检查 Android SDK
if not defined ANDROID_SDK_ROOT (
    if not defined ANDROID_HOME (
        echo [错误] 未设置 Android SDK 路径
        echo 请先安装 Android Studio 并设置 ANDROID_SDK_ROOT 环境变量
        pause
        exit /b 1
    )
)

echo [3/6] 检查 Android SDK... OK

echo.
echo [4/6] 安装依赖...
call npm install
if errorlevel 1 (
    echo [错误] 安装依赖失败
    pause
    exit /b 1
)

echo.
echo [5/6] 同步 Capacitor...
call npx cap sync android
if errorlevel 1 (
    echo [错误] 同步失败
    pause
    exit /b 1
)

echo.
echo [6/6] 构建 APK...
cd android
if not exist gradlew (
    echo 正在生成 Gradle wrapper...
    call gradle wrapper
)

call gradlew assembleRelease --no-daemon

if errorlevel 1 (
    echo.
    echo [错误] 构建失败
    cd ..
    pause
    exit /b 1
)

cd ..

echo.
echo ==========================================
echo   APK 构建成功！
echo ==========================================
echo.
echo 输出路径: android\app\build\outputs\apk\release\app-release-unsigned.apk
echo.
echo 注意: 这是未签名的 APK，如需发布请进行签名
echo.
pause
