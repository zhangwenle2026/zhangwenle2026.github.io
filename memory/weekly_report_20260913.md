# 2026-09-13 周报定稿 (BRT 9.7-9.13)

## 本期周报（已保存/已发布）
- **文档**: SP Metropolitan Weekly Review 圣保罗都市圈周报 (BRT 9.7-9.13)
- **链接**: https://km.sankuai.com/collabpage/2786831023
- **contentId**: 2786831023（父文档 2762619043 下的新建子文档）
- **状态**: 用户 09:16 确认"先保存"——即当前版本为定稿v1，后续有 BDM Excel 再更新

## 排版血泪教训（重要！updateDocumentByMd 表格坑）
1. **`updateDocumentByMd` 不支持 `:::table` 宏**：表格宏会被当纯文本塞进 `<p>`，渲染成一坨带 `:::table<br/>` 的乱文。用户报告"内容都是乱的"就是这个原因。
2. **正确做法**：走 `updateDocumentByXml` 路径，用原生 `<table>/<tr>/<th>/<td>` 节点。参考 ~/.openclaw/skills/citadel/references/doc-xml-syntax.md
3. **md表格cell内禁用竖线 `|`**：BDM排名"Tadeu 32.1% | Adriana 30.6%"把4列表拆成14列，ProseMirror校验报错。cell内用"；"分隔。
4. **`$` 符号触发 latex_inline**：`R$500` 两个$配对后中间文字变latex乱码。全部替换为全角 `R＄`（视觉几乎一致）。
5. **图片节点必须在 `<p>` 内**：`<img>` 直接放 doc/table 下会报 "image 不合法"。
6. **URL 属性中 `&` 必须 `&amp;`**（isNewContent=false 等参数）。
7. **shell heredoc 被 M_SPANID 污染**：写脚本一律用 write 工具，不要 cat <<EOF。
8. /tmp 下的 inspect.py 会 shadow 标准库，先 rm 再跑 python。

## 本期数据快照
- BML(9.12口径): SPU 15.2% (1,345/8,859), 商户 15.3% (336/2,196); BDM: Tadeu 32.1% > Adriana 30.6% > Fernando 20.6% ... Thiago 2.2%; 城市: Southern 22.4% > Santos 8.2% > Western 7.4%; _other_组10BD/1,241SPU/25.9%未归属
- 拜访(9.7-9.12): 1,854次, 线下率95.8%, 人均4.6/BD/天; Santos 4.8 > Western 4.7 > Southern 4.4
- 竞对: 164提及(99×73, Red×45, Yellow×24, iFood×22); 10家主表外新风险(Bun Smash Burger R＄700K Yellow疑似失守等, 9/10集中Western)
- 9月KRI新框架: BML 25% > Orders 20% > NS 15% = OpRate 15% = CI 15%, Mgmt 10%
- 图表: 6张 (BML BDM/城市/看板大图/每日拜访/区域/竞对提及), 均在 charts/ 下

## 数据与工具存档
- 数据目录: ~/.openclaw/workspace/projects/1_weekly_report/data/20260913/
- BML数据: bml_org_summary.json (Supabase RPC, key在/tmp/sb_key.txt, 需重新提取如果丢失)
- BML看板图: charts/bml_dashboard.jpg (城市×BDM 4视图, 已上传文档 255640943397)
- XML生成器: /tmp/md_to_xml3.py (md→CitadelXML, 可复用)

## 待办（下期/数据到位后）
- [ ] BDM Excel到了更新: KRI表Orders/NS/OpRate/CI四行首周数据 + 城市级汇总表 + 绩效Wiki(2782863123)9月版
- [ ] 待用户确认: ①10家新风险商户是否补进防守主表(2785584992) ②_other_组10个BD归属
- [ ] S2重点任务列表用户说会后续告知（本期只放了BML）
