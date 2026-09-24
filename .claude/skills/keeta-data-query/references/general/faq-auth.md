# FAQ - 鉴权与登录

[← 返回目录](faq.md)

---

### Q5：当前登录链路是什么？
非看板业务调用统一交给 mtcli 登录态处理，包括标准数据集、Hive、元数据找表、Origin 血缘、XT ETL 和埋点上报。

只有少数 mtcli schema 明确要求 `access-token` header 时，脚本才会走 mtsso + CIBA 的显式 token 兜底。CatDesk 换票、直接读取浏览器业务 Cookie、直接请求 BI/RAG/DataMap HTTP 接口都不再作为常规链路。

看板取数是唯一仍依赖浏览器页面登录态的链路，因为它读取的是 `bi.keetapp.com` 页面本身。

---

### Q6：SSO 鉴权失败怎么办？
先检查 mtcli SSO 状态：

```bash
mtcli auth sso whoami
```

如果没有返回当前用户，重新登录：

```bash
mtcli auth sso login
```

若报 `tokenPairs is null`、401、`SSO鉴权错误`，通常也是 mtcli SSO 缓存或本地代理干扰。可临时清空代理后重试：

```bash
HTTP_PROXY="" http_proxy="" HTTPS_PROXY="" https_proxy="" mtcli auth sso whoami
```

---

### Q7：Hive 明明有权限但仍报无权限？
先确认使用了正确项目空间：

```bash
kdata hive spaces
kdata hive run "SELECT ..." --project <项目空间ID>
```

个人空间、项目空间和表权限是分开的。若所有空间都无权限，Hive 命令会尽量输出表权限申请链接；按链接申请表权限，并注意选择所需 Region 和较长有效期。

---

### Q8：BI 看板页面登录失效怎么办？
看板取数依赖浏览器页面。若页面跳到登录页或无法读取：

1. 在可见浏览器中打开 `bi.keetapp.com` 并完成登录。
2. 回到 AI 对话重新执行看板取数。
3. 如果是沙箱网络问题，按 [Q18](faq-limitations.md#q18bi-看板取数有什么限制) 的限制处理。

这只影响 BI 看板自动化；标准数据集、Hive 和元数据查询不应要求浏览器页面登录。
