---
name: add-meet-prod
description: 通过 263 安全会议正式环境（sec.263.net）HTTP 接口自动登录、创建会议，并添加主持人、嘉宾和参会人；用户未指定主持人/嘉宾时使用正式环境默认人员，创建后自动添加；中断后继续时先查会再创建、已加成员自动跳过。用户提到 263 正式创会、sec.263.net、正式环境创会 curl、saveOrUpdateCloudMeet.do、addMemberList.do、addWhiteList.do、正式环境批量加人时使用。
---

# 263 安全会议（正式环境）：HTTP 接口创会/查会与加人

## 适用范围

使用 `alpha-saas-app/.agent/263创会curl` 抓包得到的 **正式环境** 后台接口完成：

1. 登录 `POST https://sec.263.net/login`
2. 创建会议 `POST /cloudmeet/saveOrUpdateCloudMeet.do`，或按会议名称和日期查找已有会议
3. 添加主持人/嘉宾 `POST /cloudmeet/addMemberList.do`
4. 添加参会人到会议级白名单 `POST /cloudmeet/addWhiteList.do`
5. 查询会议、成员、白名单列表确认结果

与测试环境 skill `add-meet-test`（`sectest.263.net`）流程一致，仅 **域名、默认账号、创会默认字段、默认主持人/嘉宾** 不同。

若用户要求走页面操作，改用浏览器版 `263-safe-meeting-book-config`（正式后台 `https://sec.263.net/querySafemeeting`）。

## 安全约定

- 本地 skill 使用正式环境抓包 curl 中的固定账号和密码哈希；不要把该 skill 副本提交到公开仓库。
- 若用户提供新账号，优先使用参数或环境变量 `SAFEMEETING_USERNAME` / `SAFEMEETING_PASSWORD_HASH` 覆盖默认值。
- 抓包里的 `JSESSIONID` 只是一时会话，禁止复用为自动化依据。
- **正式环境会创建真实会议**，执行前确认用户意图；测试请用 `add-meet-test`。

## 参数映射（相对测试环境的差异）

| 项 | 正式环境（本 skill） | 测试环境（add-meet-test） |
|----|----------------------|---------------------------|
| 基址 | `https://sec.263.net` | `https://sectest.263.net` |
| 默认账号 | `lvchen01@rabyte.cn` | `zhaoxg02@rabyte.cn` |
| 创会 `hostNumber` | `18000000001` | 空 |
| 创会 `hostEmail` | `123@qq.com`（可用 `--host-email` 覆盖） | 默认登录邮箱 |
| 默认主持人 | 杨欣 `17600215916` | 杨欣 `17600215916` |
| 默认嘉宾 | 测试观众 `13772400120`，组织「测试观众组织」 | 测试嘉宾 `13772400120` |

其余规则与 `add-meet-test` 相同：

- 会议默认值：标题 `测试会议`，开始时间为当前时间后 20 分钟，时长 `120` 分钟
- 公开会议：`--meeting-privacy open`，`whiteListValidRange=buyerOpen,platformOpen,orgWhiteList,calloutList,specialList`
- 小范围会议：`--meeting-privacy limited`，`whiteListValidRange=calloutList,specialList`
- 主持人 `role=1`，嘉宾 `role=2`，参会人走 `addWhiteList.do`

## 使用脚本

```bash
python3 ~/.cursor/skills/add-meet-prod/scripts/create_safe_meeting.py \
  --title '测试会议' \
  --start-time '2026-06-02 18:30:00' \
  --duration 120
```

指定主持人和嘉宾：

```bash
python3 ~/.cursor/skills/add-meet-prod/scripts/create_safe_meeting.py \
  --title '多嘉宾的会议' \
  --hosts-json '[{"name":"杨欣","phone":"17600215916"}]' \
  --guests-json '[{"name":"测试观众","phone":"13772400120","company":"测试观众组织"}]'
```

给已有会议加人：

```bash
python3 ~/.cursor/skills/add-meet-prod/scripts/create_safe_meeting.py \
  --existing-title '测试会议' \
  --meeting-date '2026-06-02'
```

未传 `--hosts-json` / `--guests-json` 时自动添加正式环境默认主持人和嘉宾；传 `'[]'` 可跳过该类人员。

输出 JSON 字段含义与 `add-meet-test` 相同（`meetId`、`mode`、`createSkipped`、`added.*.confirmed` 等）。

## 异常中断后继续

与 `add-meet-test` 相同：

1. **复用上次完整参数**（尤其 `--title`、`--start-time`），不要重新生成默认开始时间。
2. 重跑脚本：先 `queryMeetListByDay.do` 查重，再决定是否创会；加人前查成员/白名单，已存在则 `skipped: true`。
3. 向用户汇报跳过创会、跳过加人、本次新加结果。

仅当用户**明确要求再建一场同名新会议**时，才改 `--title` 或 `--start-time`。

## 执行流程

1. 确认用户要操作 **正式环境**（`sec.263.net`），而非测试环境。
2. 整理会议信息或使用 `--existing-title` + `--meeting-date`。
3. 运行 `add-meet-prod` 脚本；检查 `meetId`、各条 `confirmed`。
4. 失败时反馈接口响应摘要；遇验证码/二次认证则停止并让用户手动登录或重新抓包。

## 参考抓包

项目内正式环境 curl 示例：`alpha-saas-app/.agent/263创会curl/`（登录、创会、加人、查询列表）。
