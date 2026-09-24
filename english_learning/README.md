# English Learning 英语学习目录

## 目录结构
- `versions/` — 定版存档（按日期+主题命名，不再改动）
- `9.2_training/` — 9.2培训《如何应对竞争对手》工作目录（源文件、脚本、数据、模板）

## 已发布页面
| 日期 | 主题 | 链接 | UUID | 存档 |
|---|---|---|---|---|
| 2026-09-03 | 9.2培训 如何应对竞争对手 (v1 定版) | https://html-hosting-hub.mynocode.host/#/preview/8b18b0a9-5a9a-4857-bc39-1633d2a67a9c | 8b18b0a9-5a9a-4857-bc39-1633d2a67a9c | versions/2026-09-02_9.2_competition_training_v1.html |

## 页面功能（标准配置）
- 三行对照：英文原句 / 译（中文逐句翻译）/ 🈶（中文谐音）
- 🔊 单句播放（Web Speech API，需 Chrome/Edge/Safari）
- 点英文句子 = 整段连读；▶ 整段连读按钮
- 语速 0.6x / 0.8x / 1x / 1.15x
- 翻译/谐音显示开关（自测模式）
- 按时间10分钟分段的目录

## 制作流程（可复用）
1. 原始转录 txt → `clean.txt`（去 [São Paulo...] 前缀）→ `merge.py` 合成块（≥60字符+句末标点成块）→ `blocks.txt`
2. `split.py` 分3份 → subagent 并行翻译（输出 text/cn/note）
3. `xieyin.py` 字母组→汉字谐音 + 句子切分 → `final_data.json`
4. subagent 逐句翻译（以整段翻译为基准切分）→ `merge_sent_cn.py` 合并
5. `build.py` 注入 `template.html` 的 `/*__DATA__*/[]` → `training_english.html`
6. 发布：`python3 /root/.openclaw/skills/keeta-data-html-publish/scripts/publish.py publish <html> --mis zhangwenle --creator-name "张文乐" --name <name> [--update <uuid>]`
7. 定版 → 复制到 `versions/`

## 用户偏好
- 用培训会议记录学英语
- 谐音风格：字母组映射汉字（tion→申 等），整词空格分隔
- 更新已发布页面用相同 UUID（--update）
