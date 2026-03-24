• 下面是一份“Windows → NAS 反向 SSH 隧道（Reverse Tunnel）”使用说明，给另一个 Codex 直接照做即可。

## 目标

- 让 Windows 在外网/公司网 主动连回你的 NAS（fnos.dandanbaba.xyz），并在 NAS 上开一个仅本机可用的端口（如 127.0.0.1:22223）。
- 之后 在 NAS 上 用 ssh -p 22223 admin@127.0.0.1 登录 Windows。

———

## A. Windows 侧（启动隧道）

1. 确认 Windows OpenSSH Server 在运行（PowerShell）：

Get-Service sshd
Test-NetConnection 127.0.0.1 -Port 22

2. 启动反向隧道（推荐端口 22223；优先用 -p 22，如你家里用 60022 也可替换）：

ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 `
-p 22 yuanhaizhou@fnos.dandanbaba.xyz `
-R 127.0.0.1:22223:127.0.0.1:22

说明：

- 这个窗口不要关；关掉就等于停止隧道。
- -R 127.0.0.1:22223:... 让端口只在 NAS 本机可用（更安全，不会对外暴露）。

———

## B. NAS 侧（验证隧道 + 登录 Windows）

1. 确认端口已监听：

ss -lntp | rg ':22223'

2. 登录 Windows（已验证用户是 admin）：

ssh -p 22223 admin@127.0.0.1

需要跑命令（给 Codex 用）：

ssh -p 22223 admin@127.0.0.1 'whoami && hostname'

———

## C. 常见故障排查

- NAS 有 :22223 监听但登录时报 kex_exchange_identification：通常是 Windows 侧转发目标 127.0.0.1:22 不通/被占用。回 Windows 执行：

Test-NetConnection 127.0.0.1 -Port 22
Get-NetTCPConnection -LocalPort 22 -State Listen | Select LocalAddress,OwningProcess
- 公司网挡 60022：把 -p 60022 改为 -p 22。

———

## D. 停止

- 直接在 Windows 把那条 ssh -N ... 进程 Ctrl+C / 关窗口即可；NAS 上 :22223 会消失。

