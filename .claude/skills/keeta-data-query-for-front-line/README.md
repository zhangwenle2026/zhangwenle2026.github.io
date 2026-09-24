# keeta-data-query-for-front-line

Keeta 前线数据查询 Skill，面向无总部数据权限的一线用户。

## Runtime

- Python entrypoint: `python3 scripts/kdata_fl.py ...`
- Installed CLI: `kdata-fl`
- Standard dataset and org permission APIs are delegated to `mtcli kdata standard ...`.
- Compatibility wrapper: `python3 scripts/kdata.py ...`
- Required npm packages are listed in `package.json`; runtime also auto-checks `@dp/mtcli`.

## Example

```bash
python3 scripts/kdata_fl.py task start --input "查订单量"
python3 scripts/kdata_fl.py whoami
python3 scripts/kdata_fl.py task end --output "已返回权限画像"
```
