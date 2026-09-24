# Island 杂志风格 UI 设计规范

## 设计哲学

**暗底浮光（Dark Canvas, Light Content）** — 纯黑画布上，内容如浮光跃出。沉浸式高端旅行杂志质感，灵感来源 Lonely Planet 纸质杂志 + 现代 editorial web。

核心关键词：**沉浸、克制、高级感、杂志封面冲击力**

---

## 色彩系统

```
背景        #000000        纯黑，沉浸感
主文字      #FDFBF7        温暖米白（Cream），非刺眼纯白
唯一强调色  #D4A853        金色，仅点缀用（标题装饰、hover、分隔线）
辅助文字    rgba(255,255,255,0.6)   副标题、说明
```

原则：极度克制用色。金色只点缀，绝不大面积使用。

---

## 字体系统（三层结构）

| 层级 | 字体 | 字重 | 字号 | 用途 |
|---|---|---|---|---|
| Display | Playfair Display | 900 Black | 64–140px | 主标题、Hero 大字 |
| Editorial | Libre Baskerville | Italic 400 | 11–14px | 副标题、引语、slogan |
| UI | Inter | 300–600 | 9–12px | 导航、标签、按钮 |

Display 层要大到有「杂志封面」冲击力；Editorial 层要有手写感的优雅斜体。

---

## 布局架构

### Hero 区（100vh 全屏）
- 全屏背景图轮播，`object-fit: cover`
- 暗色渐变遮罩覆盖（保证文字可读）
- 居中大标题 + 斜体副标题 + 玻璃态 CTA 按钮

### 内容区（杂志架 Magazine Shelf）
- 卡片网格：桌面 4 列，移动端 2 列
- 卡片尺寸：宽 240px，高宽比 **3:4**（竖版杂志封面）
- 整体大留白，呼吸感

---

## 卡片设计

```css
/* 基础 */
border-radius: 12px;
overflow: hidden;
box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);

/* Hover：3D 翻书效果 */
transform: perspective(1000px) rotateY(-5deg) scale(1.03);
box-shadow: 0 8px 40px rgba(212, 168, 83, 0.15);
```

卡片内容：封面图（全出血）+ 底部渐变遮罩 + 城市名 + 期号

---

## 按钮（玻璃态 Glassmorphism）

```css
background: rgba(255, 255, 255, 0.08);
backdrop-filter: blur(12px);
border: 1px solid rgba(255, 255, 255, 0.15);
border-radius: 24px;
color: #FDFBF7;
padding: 8px 20px;
font-family: 'Inter', sans-serif;
font-weight: 400;
font-size: 11px;
letter-spacing: 1.5px;
text-transform: uppercase;
```

Hover：`background: rgba(255, 255, 255, 0.12)` 微微提亮即可。

---

## 返回按钮

极简胶囊样式：`← ISLAND`
- 半透明磨砂背景
- 细箭头 + 品牌名
- 无 emoji，无多余装饰

---

## 动效

| 元素 | 效果 | 参数 |
|---|---|---|
| 背景轮播 | crossfade 淡入淡出 | 5s 间隔，1s 过渡 |
| 卡片入场 | fade-up | `translateY(30px)→0`，stagger 100ms |
| 卡片 hover | 3D tilt | perspective 1000px，±5° 旋转 |
| 页面切换 | 整体 fade | 300ms ease |

动效原则：克制、有目的，服务于内容而非炫技。

---

## 响应式

- Hero 标题：桌面 80–140px → 移动 40–60px
- 卡片网格：桌面 4 列 → 平板 3 列 → 移动 2 列
- 背景图：始终 `100vw × 100vh`，`object-fit: cover`，焦点居中

---

## Do's & Don'ts

✅ **Do**
- 大留白，呼吸感
- 图片全出血（edge-to-edge），无边框
- 暗色渐变遮罩 + 白字确保可读性
- 文字层级分明（三层字体各司其职）
- 动效服务于浏览节奏

❌ **Don't**
- 堆砌元素
- 图片加边框或圆角过大
- 大面积使用金色
- 所有文字一个大小
- 在亮图上直接放白字（没遮罩）
- 为了炫技加无意义动画

---

## 整体氛围一句话

> 打开页面的感觉，像在深夜翻开一本 Lonely Planet 精装特刊——安静、沉浸、每一页都想停下来看。
