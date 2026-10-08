# 交付清单

- [x] **响应式首屏与双行标题：** 建立相对定位、`z-10`、纵向 flex 置中且文字置中的首屏版面，使用 `px-5 sm:px-8 pt-12 sm:pt-16 md:pt-24`；以 Garamond 显示两行 `WITNESS THE` 和 `HIDDEN REALM`，套用 `4xl/6xl/8xl/9xl` 响应式字级、`font-normal`、白色、`1.08` 行高、紧凑字距及 `mb-6 sm:mb-8`。
- [x] **逐字符 StaggeredFade 动画：** 建立接收 `text` 字串 prop 的组件；拆为个别 `motion.span`；使用 `useInView({ once: true })`；每个字符从 opacity 0 淡入 opacity 1 / `y:0`，延迟为 `i × 0.07s`，并让两行标题都使用此组件。
- [x] **副标题入场与响应式换行：** 加入文本 `An odyssey through delicate living forms,` / `revealed by lens and curiosity.` 的 Framer Motion 段落，从 `opacity:0, y:20` 进入 `opacity:1, y:0`，`duration:0.8s`、`delay:1.6s`；移动端隐藏断行、`sm` 以上显示；使用指定 white/70、font-light、leading-relaxed、最大宽度、下边距和响应式文本尺寸。
- [x] **液态玻璃 CTA：** 加入文字 `Begin the Experience` 的 Framer Motion CTA，从 `opacity:0, y:20` 进入 `opacity:1, y:0`，`duration:0.8s`、`delay:2.0s`；采用 `.liquid-glass`、rounded-full、`px-7 sm:px-10 py-3.5 sm:py-4`、white/90、uppercase 与指定响应式字距；实现玻璃背景、luminosity、4px backdrop blur、内阴影、渐变遮罩描边、hover 和 active 状态。
- [x] **全局样式与交付运行环境：** 通过 `@tailwind base/components/utilities`、全局 margin/padding/box-sizing reset、`#010101` 深色 body 与白字抗锯齿完成样式；创建 `/manus-routes.json`；项目可在 `0.0.0.0:3000` 构建和运行。
