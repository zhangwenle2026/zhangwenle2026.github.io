# 🗺️ BML Battle Map — AI 构建手册

> 这是一份完整的竞争监控仪表板构建 Playbook，记录了从 0 到 1 用 AI + NoCode + Supabase 搭建管理层竞争情报看板的全过程。其他 AI 或开发者可以直接参考复现。

---

## 🎯 产品定位

**场景**：外卖平台 BD 团队，需要实时监控竞争对手（99Food）对商家的渗透情况，帮助管理层快速识别高风险区域、高风险 BDM，并按优先级分配资源。

**核心问题**：
- 哪些 BDM 管辖的商家正在被竞争对手攻占？
- 哪些商家已经签了竞对独家合同？
- 哪些商家正在被竞对积极谈判？

**用户**：SP Metropolitan 管理层（非技术用户，需要扫一眼就能抓重点）

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────┐
│          React + ECharts 前端            │
│  (NoCode 低代码平台托管，Vite 构建)       │
├─────────────────────────────────────────┤
│         Supabase (PostgreSQL)            │
│  merchants 表 + daily_snapshots 表       │
├─────────────────────────────────────────┤
│            自定义域名托管                  │
│      *.mynocode.host                     │
└─────────────────────────────────────────┘
```

**技术选型理由**：
- **NoCode**：快速搭建，AI 可直接生成代码并部署，无需配置服务器
- **Supabase**：提供 REST API，前端直接查询，无需后端服务
- **ECharts**：热力图、折线图能力强，适合竞争矩阵可视化

---

## 📊 数据模型设计

### merchants 表（核心表）

```sql
CREATE TABLE merchants (
  id              SERIAL PRIMARY KEY,
  store_id        TEXT,
  store_name      TEXT NOT NULL,
  city            TEXT,          -- 区域分组：Northeast/Southern/Western São Paulo
  aor             TEXT,          -- 小区
  bdm_name        TEXT,          -- 负责 BDM 姓名
  competition_status TEXT,       -- 竞争状态（见枚举）
  has_99_contract BOOLEAN DEFAULT FALSE,  -- 是否已签 99 合同
  keeta_orders    INTEGER DEFAULT 0,      -- Keeta 平台历史单量
  aov             NUMERIC,       -- 客单价
  bml_score       NUMERIC,       -- BML 评分
  atitude_kp      TEXT,          -- KP 态度描述
  is_important    BOOLEAN DEFAULT FALSE,
  bd_feedback     TEXT,
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

**competition_status 枚举值**（按风险从高到低）：
| 值 | 含义 | 颜色 |
|----|------|------|
| `signed_exclusive` | 已签竞对独家 | 🔴 红 |
| `negotiating` | 竞对正在谈判 | 🔵 蓝 |
| `rejected` | 已拒绝竞对 | 🟡 黄 |
| `contacted` | 已被竞对接触 | 青 |
| `not_contacted` | 未被接触 | 灰 |

### daily_snapshots 表（趋势数据）

```sql
CREATE TABLE daily_snapshots (
  id               SERIAL PRIMARY KEY,
  snapshot_date    DATE NOT NULL,
  city             TEXT DEFAULT 'All Regions',
  total_merchants  INTEGER,
  signed_exclusive INTEGER DEFAULT 0,
  has_99_contract  INTEGER DEFAULT 0,
  negotiating      INTEGER DEFAULT 0,
  rejected         INTEGER DEFAULT 0
);
```

> 💡 每天跑一个脚本把 merchants 表聚合一条快照插进来，就能看到趋势。

---

## 🧠 核心业务逻辑

### 1. 风险等级计算

```javascript
// 商家维度
function computeRiskScore(merchant) {
  const status = merchant.competition_status;
  const has99  = merchant.has_99_contract === true;

  if (status === "signed_exclusive")          return 3; // 🔴 High — 已失守
  if (status === "negotiating" && has99)      return 3; // 🔴 High — 双重威胁
  if (has99 || status === "negotiating")      return 2; // 🟡 Medium — 需关注
  return 1;                                              // 🟢 Low
}

function riskLabel(merchant) {
  const s = computeRiskScore(merchant);
  if (s === 3) return "high";
  if (s === 2) return "medium";
  return "low";
}
```

### 2. BDM 风险矩阵热力图评分

```javascript
// BDM 维度：聚合旗下所有商家
const riskScore = bdm.signed_exclusive * 3
                + bdm.has_99_contract  * 2
                + bdm.negotiating      * 1;

// 热力图 4 列：
// Col 0: Exclusive (n)       — 绝对数量，深红色阶
// Col 1: Has 99 %            — 占比，橙色色阶
// Col 2: Negotiating %       — 占比，橙色色阶
// Col 3: Rejected %          — 占比，橙色色阶
```

### 3. 双色阶热力图实现（ECharts）

关键技巧：**拆成两个 series + 两个 visualMap**，分别控制颜色：

```javascript
// 数据分开
const exclData  = [];  // 只放 col 0
const otherData = [];  // col 1-3

// 两个 visualMap
visualMap: [
  {
    seriesIndex: 0,   // Exclusive 列 — 深红
    min: 0, max: 5,
    inRange: { color: ["#FFF5F5", "#FFCDD2", "#EF9A9A", "#E53935", "#B71C1C"] },
  },
  {
    seriesIndex: 1,   // 其他列 — 橙色
    min: 0, max: 60,
    inRange: { color: ["#FFF8F5", "#FFCBA4", "#FF8C42", "#E65100", "#BF360C"] },
  },
],
series: [
  { type: "heatmap", data: exclData  },  // series 0
  { type: "heatmap", data: otherData },  // series 1
]
```

> ⚠️ **踩坑**：ECharts heatmap 的 `itemStyle.color` **不支持函数**，只能通过 visualMap 驱动颜色。多列不同颜色必须拆 series。

### 4. CRM 列表排序

```javascript
// 先按风险降序，同级内按单量降序
merchants.sort((a, b) => {
  const rd = computeRiskScore(b) - computeRiskScore(a);
  if (rd !== 0) return rd;
  return (b.keeta_orders ?? 0) - (a.keeta_orders ?? 0);
});
```

---

## 🎨 UI 设计原则

### 信息层级
```
L1 总览卡片（6个 KPI 数字）
  └── L2 Tab 切换（BML Battle Map / CRM / SK Library）
        └── L3 城市 Tab 过滤（All / Northeast / Southern / Western）
              └── L4 点击 BDM 行 → 该 BDM 下的商家列表
```

### 颜色语义（全局统一）
| 颜色 | 含义 |
|------|------|
| 🔴 深红 `#B71C1C` | 最高风险：已失守/独家 |
| 🟠 橙红 `#E65100` | 高风险：谈判中/99合同 |
| 🟡 黄 `#FFC107` | 中风险：已拒绝但曾接触 |
| 🔵 蓝 `#2196F3` | 活跃谈判中 |
| 🟢 绿 `#4CAF50` | 低风险/安全 |

### 热力图设计选择
- **气泡图 → 热力图**：气泡图适合探索，热力图适合管理层快速扫描矩阵
- **Y 轴翻转**：风险最高的 BDM 在最顶部，符合阅读习惯
- **绝对数 vs 百分比**：Exclusive 列用绝对数（n），因为"3个独家"比"50%独家率"更直观；其他列用百分比，方便跨 BDM 比较

### CRM 列表 vs 卡片
- **卡片**：适合详情浏览，信息丰富但密度低
- **列表**：适合管理层快速扫描，一屏能看到更多商家，优先级一目了然
- 选择**列表**：管理场景下需要快速识别 Top N 风险商家

---

## 🔧 数据质量处理

实际业务中数据往往不完整，处理策略：

| 字段 | 填充率 | 处理方案 |
|------|--------|---------|
| keeta_orders | 91% | 作为主要指标，排序依据 |
| aov | 27% | 有值才显示，0 不渲染格子 |
| bml_score | 18% | 有值才显示 |
| atitude_kp | 37% | 有值才显示 |
| risk（DB字段）| 1% | **废弃**，改为前端动态计算 |
| has_bd_feedback | 1% | **废弃**，不展示进度条 |
| orders_day | 含异常值(42000) | **废弃**，改用 keeta_orders |

> 💡 **原则**：宁可显示少，不显示错。0 和 null 不等于数据，不应该占版面。

---

## 🚀 AI 构建工作流

整个仪表板由 AI（CatClaw/Claude）驱动构建，工作流如下：

```
用户说"我要改 X" 
  → AI 读取代码文件
  → AI 分析数据结构
  → AI 直接编辑代码
  → git commit + push
  → nocode code pull --force
  → nocode deploy
  → agent-browser 截图验证
  → 发给用户确认
```

**关键工具**：
- `read` / `edit` / `write` — 直接操作代码文件
- `exec` — 运行 git / nocode CLI 命令
- `agent-browser` — 自动化截图验证，不用人工刷新确认

**最高效的迭代方式**：
1. 用 NoCode AI Agent 生成初始代码（自然语言描述需求）
2. Agent 卡住或功能复杂时，切换到直接 git 编辑模式
3. 每次改动用截图验证，快速发现问题
4. 数据问题（异常值、字段映射错误）要在 DB 层和展示层双重处理

---

## 📋 可复用的 UI 组件模式

### 状态 Badge
```jsx
const StatusBadge = ({ status }) => {
  const map = {
    signed_exclusive: { label: "Exclusive",     color: "#FF4444" },
    negotiating:      { label: "Negotiating",   color: "#2196F3" },
    rejected:         { label: "Rejected",      color: "#FFC107" },
    contacted:        { label: "Contacted",     color: "#00BCD4" },
    not_contacted:    { label: "Not Contacted", color: "#9E9E9E" },
  };
  const s = map[status] || { label: status, color: "#999" };
  return (
    <span style={{
      padding: "2px 8px", borderRadius: 12, fontSize: 11, fontWeight: 600,
      background: `${s.color}18`, color: s.color, border: `1px solid ${s.color}40`,
    }}>
      {s.label}
    </span>
  );
};
```

### 风险 Badge
```jsx
const RiskBadge = ({ level }) => {
  const map = {
    high:   { text: "🔴 High Risk", bg: "#FFF0F0", color: "#D32F2F", border: "#FFCCCC" },
    medium: { text: "🟡 Medium",    bg: "#FFF8E1", color: "#F57F17", border: "#FFE082" },
    low:    { text: "🟢 Low",       bg: "#F1F8E9", color: "#388E3C", border: "#C8E6C9" },
  };
  const s = map[level] || map.low;
  return (
    <span style={{
      padding: "2px 8px", borderRadius: 12, fontSize: 11, fontWeight: 600,
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
    }}>
      {s.text}
    </span>
  );
};
```

### 小样本警告
```jsx
// 热力图底部：当有 BDM 样本量 < 5 时展示
{bdmData.some(b => b.total < 5) && (
  <p style={{ color: "#F90", fontSize: 11, marginTop: 8 }}>
    ⚠ BDMs with n&lt;5 merchants — percentages may not be representative
  </p>
)}
```

---

## 💡 设计决策记录（供后来者参考）

| 决策 | 选择 | 原因 |
|------|------|------|
| 竞争矩阵可视化 | 热力图 | 比气泡图更适合管理层快速矩阵扫描 |
| Exclusive 列颜色 | 独立深红色阶 | 语义上是最严重的信号，需要视觉上突出区别 |
| 风险计算 | 前端动态计算 | DB 字段填充率1%，不可用；前端计算更灵活可控 |
| 数据排序 | 风险降序+单量降序 | 最重要的商家永远在第一眼看到的位置 |
| CRM 视图 | 列表 > 卡片 | 管理场景：扫描 > 浏览 |
| orders_day 字段 | 废弃 | 含异常值(42000)，不可信，改用 keeta_orders |
| 城市过滤 | Tab 式 | 比下拉框更直观，切换成本更低 |

---

## 🔗 相关资源

- **Live Demo**: https://battle-map-insight.mynocode.host
- **Latest Version**: `9e9f07a`
- **Tech Stack**: React + ECharts + Supabase + NoCode (美团内部低代码平台)
- **Build Tool**: CatClaw AI (OpenClaw) — 全程 AI 驱动迭代

---

*构建时间：2026年6月 | 平台：Keeta SP Metropolitan | 迭代轮次：15+*
