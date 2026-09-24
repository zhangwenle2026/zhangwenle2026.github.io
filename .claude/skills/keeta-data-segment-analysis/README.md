# keeta-data-segment-analysis

用户生命周期分层指标监控 Skill，当前支持 AE（UAE）区域 DBR 场景。

## 目录结构

```
keeta-data-segment-analysis/
├── SKILL.md                              # Skill 元信息 + 使用说明
├── README.md                             # 开发者文档（本文件）
├── requirements.txt                      # Python 依赖声明
├── scripts/
│   ├── ae_dbr_query.py                   # AE DBR 查询脚本（主入口）
│   ├── ae_dbr_chart.py                   # 可视化图表生成脚本
│   └── bi_client.py                      # BI 接口通信模块
└── references/
    └── scenarios/
        └── dbr_lifecycle_monitoring.md   # DBR 场景 SQL 定义 + 输出格式
```

## 环境搭建

```bash
# 在 skill venv 中安装依赖
~/.claude/skills/keeta-data-segment-analysis/.venv/bin/pip install -r requirements.txt
```

## 新增固化场景

1. 在 `references/scenarios/` 下新建场景文档，参考 `dbr_lifecycle_monitoring.md` 格式
2. 在 `scripts/` 下新建对应查询脚本
3. 在 `SKILL.md` 的「固化场景索引」和「Step 1：识别场景」表格中注册新场景

## 维护者

- creator: mengxiangtong
