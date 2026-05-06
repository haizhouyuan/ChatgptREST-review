# OpenClawBot Mixed Work-Material Handoff Contract v1

日期：2026-04-10

## 目标

约束 `feishu-intake` 在处理“高层工作推理 + 显式本地文件路径/附件”混合 ask 时的 first action，避免入口退化成目录探测器。

## 适用范围

- 入口：`OpenClawBot` Feishu `feishu-intake`
- 任务形态：
  - 工作总结
  - 模块梳理
  - 框架设计
  - 方案/复盘/汇报
  - 同时附带显式本地文件路径或附件

## 合同

### 1. Mixed ask first action

当 ask 同时满足以下两个条件时，`feishu-intake` 必须先调用 `openmind_advisor_ask`：

- 存在高层工作推理信号：
  - `梳理`
  - `总结`
  - `模块`
  - `框架`
  - `方案`
  - `复盘`
  - `汇报`
  - `怎么做`
- 同时存在显式本地路径或附件

### 2. Local material preflight propagation

`openmind_advisor_ask` 必须自动把显式本地路径投影到 advisor lane：

- `requestContext.explicit_local_paths`
- `requestContext.local_material_preflight`
- `requestContext.local_material_preflight_summary`
- `task_intake.attachments`

### 3. `openmind_work_material_ops` 的定位

`openmind_work_material_ops` 只允许优先用于：

- 纯本地路径检查
- workbook sheet listing
- allowlisted root 内的受控移动
- advisor lane 已经定框架后的显式 follow-up file action

### 4. 禁止动作

在 mixed ask 的 first turn，`feishu-intake` 不应：

- 先扫描父目录
- 先猜归档目标
- 先做大范围目录探测
- 仅凭本地 inspection 直接生成工作总结主框架

## 运行时边界

- allowlisted read roots：
  - `/vol1/1000/projects/planning`
  - `/vol1/1000/projects/ChatgptREST`
- allowlisted write root：
  - `/vol1/1000/projects/planning`
- `exec` 不属于该 lane

## 验收

- workspace rules 明确写入 `TOOLS.md` / `AGENTS.md` / `ROLE_PACKS.md`
- plugin source 存在显式本地路径抽取与 preflight 投影
- focused tests 通过
- live gateway 重建并重启后，下一条 fresh Feishu mixed ask 不应再以目录探测作为唯一主路径
