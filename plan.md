# Cat Health Monitor 动态介绍页计划

## 目标与实现方式

在一个纯前端 Vite + React + TypeScript 项目中制作沉浸式首屏介绍页。使用 Tailwind CSS 组织响应式排版，Framer Motion 驱动逐字标题与延迟入场动画；不依赖服务端、数据库或图片资产。页面由 Vite 静态服务在 `0.0.0.0:3000` 提供，并在发布时构建为 `dist/`。

已确认的产品要求：

- 首屏为相对定位、`z-10`、垂直 flex 居中、文字居中的响应式布局，采用 `px-5 sm:px-8 pt-12 sm:pt-16 md:pt-24`。
- 使用 Garamond 的两行标题 `WITNESS THE` / `HIDDEN REALM`，套用指定的字号、白色、紧凑字距与 1.08 行高。
- `StaggeredFade` 将字符串拆为字符级 `motion.span`；进入视口仅触发一次；每个字符以 `i × 0.07s` 的延迟淡入。
- 副标题与 CTA 分别在 1.6s、2.0s 后按指定的 opacity/y/duration 进入；副标题只在 `sm` 以上显示断行。
- CTA 文案为 `Begin the Experience`，使用液态玻璃视觉和指定的响应式间距、字距与大小写。
- 全局样式提供 reset、抗锯齿白字与 `#010101` 背景，并保留 `@tailwind base/components/utilities` 指令。

## 视觉与体验方向

- **设计运动：** 暗色生物摄影的当代编辑式叙事，以深黑空间与微弱有机光晕制造“镜头发现未知生命”的开场。
- **核心原则：** 克制留白、文字即主角、以低频动态建立深度、优先可读性与键盘可达性。
- **色彩理念：** `#010101` 让白色字句像暗室中的曝光；低饱和青绿/雾蓝背景呼吸光仅用于空间层次，不与 CTA 或内容争夺注意力。
- **布局范式：** 单一垂直叙事轴，而非卡片或网格；标题位于光晕焦点，外圈以渐变与颗粒感拉开景深。
- **标志性元素：** 字符逐字显影、椭圆形液态玻璃边界、缓慢漂移的光晕/光斑。
- **交互理念：** 所有反馈都像镜头轻微调焦：CTA 在悬停时微亮，按下时缩放；减少动态偏好下自动静止。
- **动画规范：** 标题遵循 0.07s/字符的固定节律；副标题在 1.6s、CTA 在 2.0s 依序出现；环境光的运动缓慢且循环，不干扰阅读；`prefers-reduced-motion` 将所有运动降为即时呈现。
- **字体系统：** 标题与品牌语调采用 `Garamond, Baskerville, Times New Roman, serif`；说明与 CTA 采用清晰的系统无衬线字体。标题层级由 4xl 至 9xl 的响应式范围建立。
- **品牌本质：** 为好奇的观察者开启一个由镜头揭示的微观生命领域。人格：神秘、精致、好奇。
- **品牌语气：** 诗性而准确，邀请而非催促。示例：`WITNESS THE HIDDEN REALM`、`An odyssey through delicate living forms, revealed by lens and curiosity.`
- **文字标识与标志：** 用极细的单字母 `O` 形镜头光圈作为隐性标记，避免默认字标；本次首屏以大标题承担标识功能。
- **代表色：** 深渊黑 `#010101`。

## 项目结构

| 路径 | 职责 |
| --- | --- |
| `src/main.tsx` | 挂载 React 应用。 |
| `src/App.tsx` | 首屏布局、环境光、动画内容与 CTA 行为。 |
| `src/components/StaggeredFade.tsx` | 可复用的逐字符进入视口淡入组件。 |
| `src/index.css` | Tailwind 指令、全局 reset、液态玻璃、背景与无障碍降动画规则。 |
| `tailwind.config.cjs` | 扫描路径与设计 token。 |
| `public/manus-routes.json` | 网站路由清单。 |
| `vite.config.ts` | Vite 在 3000 端口、所有地址监听的开发配置。 |

## 技术与材料边界

使用 React、Framer Motion、Tailwind CSS 与 Vite；无服务端、数据库、外部 API 或图片素材。环境质感由 CSS 渐变、伪元素和动画生成，以保持加载轻量并贴合黑色摄影叙事。CTA 是可聚焦按钮，页面保留语义标题、描述和减少动态偏好支持。
