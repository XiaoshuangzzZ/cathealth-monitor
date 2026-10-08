
## 既有 CatHealth 应用整合

原仓库包含静态登录页、健康仪表盘、Flask 后端与 Capacitor 打包脚本。为避免以新介绍页覆盖可用的健康监测功能，原首页认证内容保留为 `auth.html`，CTA 改为链接至该页面；`dashboard.html`、认证脚本、地图、清单与图标则原样保留。Vite 的构建后复制脚本把这些既有静态资源同步到 `dist/`，使介绍页在 Web 预览、静态发布与 Android `www/` 打包路径中都能进入原有应用。
