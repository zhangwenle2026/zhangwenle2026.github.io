---

name: env-check

description: "bi-query-dashboard运行环境检查与安装指引"

---




# 运行环境检查与安装指引




如果当前处于 CatPaw Desk 环境，按以下要求完成环境校验及安装：




请检查并补齐环境：

1. Python3（先试 `python3`，再试 `python`，务必确保版本处于 3.8 及以上）；

2. Python 包 `playwright`；

3. Playwright 的 `chromium`。




原则：

- 先检查，缺什么装什么，不重复安装。

- 按系统区分：mac 优先用 `brew` 安装 Python；Windows 优先用 `winget`，并优先使用 `py -3`/`python`。

- 安装 `playwright` 时，优先使用大陆 pip 源：`--trusted-host=pypi.sankuai.com -i http://pypi.sankuai.com/simple/`；若失败，依次尝试阿里云、清华等国内源。

- 安装后用最小脚本验证可导入 `playwright` 且 `chromium` 能启动。

- 基于真实命令输出汇报：系统类型、缺失项、执行命令、使用的安装方式/镜像源、最终可用性；不要编造结果，失败需说明原因。
