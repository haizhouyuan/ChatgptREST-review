# AI 工具与模型执行全记录 — Labebe Wonder Room BOSS-3D-003

> 本文档记录从 2026-05-02 至 2026-05-03 期间，所有下载/使用的 AI/ML 模型、工具、生成资产、测试结果、审核结论的完整流水账。
>
> **扩展记录**: 同时涵盖 HomePC 和 Yoga 上已安装的全部模型资产（含历史安装），以及 maint 库研究过的所有大模型相关文档。
>
> 目的：供后续 agent 复现、审计、排障时直接查阅，不做任何省略。
>
> 记录人: Kimi Code CLI
> 最后更新: 2026-05-03

---

## 目录

1. [环境资产清单](#1-环境资产清单)
2. [下载的模型与工具](#2-下载的模型与工具)
3. [AI 生成资产全记录](#3-ai-生成资产全记录)
4. [测试执行记录](#4-测试执行记录)
5. [Playwright 视频录制记录](#5-playwright-视频录制记录)
6. [ChatGPT Pro 审核全记录](#6-chatgpt-pro-审核全记录)
7. [Google Drive 同步记录](#7-google-drive-同步记录)
8. [HomePC 全量模型资产清单](#8-homepc-全量模型资产清单)
9. [Yoga 全量模型资产清单](#9-yoga-全量模型资产清单)
10. [Maint 库大模型研究文档索引](#10-maint-库大模型研究文档索引)
11. [结论与决策索引](#11-结论与决策索引)
12. [已知缺陷与 TODO](#12-已知缺陷与-todo)

---

## 1. 环境资产清单

### 1.1 机器拓扑

| 机器 | IP | GPU | 用途 | 操作系统 |
|------|-----|-----|------|----------|
| Yoga | 127.0.0.1 (local) | 无 | Web/build/QA/package/sync | Debian 12 |
| HomePC | 192.168.1.17 (legacy LAN) | 2× RTX 3090 (48GB VRAM) | LLM inference / TRELLIS / ComfyUI | Ubuntu (CUDA 12.2) |
| HomePC | 192.168.31.38 (canonical LAN, 不可达) | 2× RTX 3090 (48GB VRAM) | TRELLIS GLB 生成（首选地址） | Ubuntu (CUDA 12.2) |

### 1.2 HomePC 硬件配置（详细）

| 项目 | 规格 |
|------|------|
| **GPU** | 2 × NVIDIA GeForce RTX 3090 (每张 24GB VRAM, 共 48GB) |
| **CPU** | AMD Ryzen 7 9700X 8-Core Processor |
| **RAM** | 60GB |
| **CUDA** | 12.2 |
| **驱动** | NVIDIA 535.288.01 |
| **机械硬盘** | 3.7TB NTFS (`/dev/sda2`) 挂载于 `/mnt/hdd`，已用 542GB，可用 3.2TB |
| **系统盘** | / 分区约 1.2TB |

### 1.3 代理环境

```
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
ALL_PROXY=http://127.0.0.1:7890
NO_PROXY=127.0.0.1,localhost,::1,192.168.0.0/16,10.0.0.0/8  (建议值，实际未全局设置)
```

代理客户端: mihomo/clash

### 1.4 项目根目录

```
/vol1/1000/projects/toyresearch/
├── deliverables/labebe_wonder_room_boss3d_20260502_package/   ← 本包工作目录
├── data/labebe/images/                                        ← 产品图源
├── labebe-gemini-demo/src/data/products.ts                    ← 产品数据种子
├── skills/homepc-workstation-bridge/SKILL.md                  ← HomePC 桥接技能
└── docs/                                                      ← 本文档所在目录
```

---

## 2. 下载的模型与工具

### 2.1 TRELLIS（3D 生成模型）

| 字段 | 值 |
|------|-----|
| **模型名称** | TRELLIS (microsoft/TRELLIS-image-large) |
| **模型类型** | 3D Gaussian Splatting → mesh extraction → GLB export |
| **来源** | HuggingFace: `microsoft/TRELLIS-image-large` |
| **安装位置** | HomePC (`192.168.1.17`) |
| **Conda 环境** | `trellis` |
| **Python 路径** | `~/miniconda3/bin/conda run -n trellis python3` |
| **生成脚本** | `~/trellis_generate.py` (4113 bytes) |
| **关键依赖** | torch 2.4.0+cu118, diffusers 0.37.1, transformers 5.7.0, torchvision 0.19.0+cu118 |
| **首次安装时间** | 早于 2026-05-02（非本次安装） |
| **GPU 配置** | `--gpu 1` (使用单卡) |
| **纹理分辨率** | `--texture-size 1024` |
| **种子** | `--seed 42` |
| **HomePC 输入目录** | `~/labebe-wonder-room/trellis_inputs/` |
| **HomePC 输出目录** | `~/labebe-wonder-room/trellis_outputs/` |

**生成命令模板**:
```bash
~/miniconda3/bin/conda run -n trellis python3 ~/trellis_generate.py \
  ~/labebe-wonder-room/trellis_inputs/<slug>.jpg \
  ~/labebe-wonder-room/trellis_outputs/<slug>.glb \
  --gpu 1 --seed 42 --texture-size 1024 --quiet
```

**SCP 回传命令**:
```powershell
scp yuanhaizhou@192.168.1.17:~/labebe-wonder-room/trellis_outputs/<slug>.glb \
  D:\projects\labebe-wonder-room\public\models\<slug>.glb
```

### 2.2 Playwright Chromium（浏览器引擎）

#### 2.2.1 自动安装失败记录

| 字段 | 值 |
|------|-----|
| **命令** | `npx playwright install` |
| **失败原因** | 网络超时（Playwright CDN 下载 chromium-1217 超时） |
| **代理影响** | 代理导致 CDN 连接不稳定 |
| **解决方式** | 手动下载 + symlink |

#### 2.2.2 手动安装记录

| 版本 | 状态 | 路径 | 大小 | 安装时间 |
|------|------|------|------|----------|
| chromium-1200 | 预装 | `~/.cache/ms-playwright/chromium-1200/` | 未知 | 早于本次 |
| chromium-1217 | 手动下载 | `~/.cache/ms-playwright/chromium-1217/` | 170 MB | 2026-05-03 |
| chromium_headless_shell-1200 | 预装 | `~/.cache/ms-playwright/chromium_headless_shell-1200/` | 未知 | 早于本次 |
| chromium_headless_shell-1217 | **symlink 创建** | `~/.cache/ms-playwright/chromium_headless_shell-1217/` | 0 bytes (空目录) | 2026-05-03 |

**Symlink 创建命令**:
```bash
mkdir -p ~/.cache/ms-playwright/chromium_headless_shell-1217/chrome-headless-shell-linux64
ln -sf ~/.cache/ms-playwright/chromium_headless_shell-1200/chrome-headless-shell-linux64/chrome-headless-shell \
  ~/.cache/ms-playwright/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell
```

**注意**: chromium-1217 的 `chrome-linux64/` 目录存在但为空（`total 0`），实际使用的是 chromium-1200 的 headless shell 作为 fallback。这不是干净的安装，可能在 Playwright 升级后再次出问题。

### 2.3 FFmpeg（视频处理）

| 字段 | 值 |
|------|-----|
| **来源** | 系统包管理器 (`apt`) |
| **版本** | 5.1.8-0+deb12u1 |
| **用途** | MP4 拼接、GIF 生成、分辨率压缩 |

### 2.4 rclone（云存储同步）

| 字段 | 值 |
|------|-----|
| **来源** | 预装（二进制在 `~/.local/bin/rclone`） |
| **远程配置** | `gdrive:` (Google Drive) |
| **代理配置** | 通过 scoped env 导出 |

### 2.5 ChatgptREST（Pro 审核基础设施）

| 字段 | 值 |
|------|-----|
| **安装位置** | `/vol1/1000/projects/ChatgptREST/` |
| **Python 环境** | `.venv` (Python 3.11) |
| **MCP 服务** | `127.0.0.1:18712/mcp` |
| **API 服务** | `127.0.0.1:18711` |
| **API Token** | `jPmPNFUrupyHKj7xzUmqKi8Z15aT8Wej1cBJPPqNtRg` |
| **OPS Token** | `32o0jnGEMsFpBC7UjqEYwfDe75QWppUn-c2i9UpKlkU` |
| **已知问题** | Git worktree 导致 Python 模块解析冲突 |
| **解决方式** | `PYTHONPATH=/vol1/1000/projects/ChatgptREST` |

---

## 3. AI 生成资产全记录

### 3.1 TRELLIS GLB 模型（按时间顺序）

#### Batch 1: 2026-05-02（原始 2 个 + 实验 5 个）

| # | 文件名 | 大小 | Source | 决策 | 状态 |
|---|--------|------|--------|------|------|
| 1 | `learning-tower-montessori-kitchen-tower-white.glb` | ~1.7 MB | Labebe 独立站产品图 | QA-pending | 已集成 |
| 2 | `kids-toy-storage-organizer-bookshelf-with-bins.glb` | ~1.9 MB | Labebe 独立站产品图 | 最强内部 3D QA | 已集成 |
| 3 | `learning-tower-white3-main-crop.glb` | ~1.5 MB | 裁剪后的产品信息图 | Rejected | 仅 QA 证据 |
| 4 | `learning-tower-white8-center-crop.glb` | ~1.3 MB | 裁剪后的特性图 | Rejected | 仅 QA 证据 |
| 5 | `learning-tower-white-rembg-nopre.glb` | ~1.6 MB | rembg 透明 PNG | Rejected | 仅 QA 证据 |
| 6 | `foldable-learning-tower-log-color.glb` | ~1.8 MB | Labebe 独立站图 | Candidate only | 未连接产品数据 |
| 7 | `learning-tower-white-clean-source-1024.glb` | ~1.6 MB | 白底 1024 输入 | Rejected | 仅 QA 证据 |
| 8 | `storage-organizer-source-crop-bright-1024.glb` | ~1.7 MB | 明亮裁剪输入 | QA candidate only | 仅 QA 证据 |

#### Batch 2: 2026-05-03（5 个新 SKU + 1 个 rerun）

| # | 文件名 | 大小 | Source | uniqueColors (front/3q) | 决策 |
|---|--------|------|--------|------------------------|------|
| 9 | `cream-wooden-play-kitchen-set-with-storage.glb` | 1.3 MB | Labebe 独立站 | 23 / 19 | QA-pending |
| 10 | `activity-cube-baby-push-walker.glb` | 2.1 MB | Labebe 独立站 | 16 / 15 | QA-pending |
| 11 | `crocodile-plush-rocker.glb` | 1.9 MB | Labebe 独立站 | 12 / 12 | QA-pending (frozen) |
| 12 | `pink-unicorn-plush-rocker.glb` | 1.8 MB | Labebe 独立站 | 16 / 15 | QA-pending (frozen) |
| 13 | `learning-tower-montessori-kitchen-tower-white-rerun-20260503.glb` | 1.7 MB | 原始源图 rerun | 13 / 13 | QA-pending |

**总计**: 13 个 GLB 生成，6 个已集成到 showroom，7 个仅作为 QA 证据。

### 3.2 AI 生成展厅全景图

| # | 文件名 | 来源 | 尺寸 | 用途 | 状态 |
|---|--------|------|------|------|------|
| 1 | `chatgpt-showroom-panorama-20260502.png` | ChatGPT 浏览器生成 | 2:1 | 早期实验 | 已归档 |
| 2 | `codex-empty-showroom-panorama-20260502.png` | Codex native 生成 | 2:1 | 当前 boss motion 默认 | 在用 |

### 3.3 Playwright 录制视频

| # | 文件名 | 大小 | 时长 | 分辨率 | 用途 | 生成方式 |
|---|--------|------|------|--------|------|----------|
| 1 | `boss3d-003-walkthrough-source-photo-20260503.mp4` | 5.0 MB | 54.2s | 1440×900 (desktop) + 393×852 (mobile) 拼接 | Stage 5 walkthrough | Playwright `recordVideo` + ffmpeg concat |
| 2 | `boss3d-003-walkthrough-source-photo-20260503.gif` | 6.8 MB | 54.2s | 480×? (lanczos 缩放) | GIF 摘要 | ffmpeg |
| 3 | `boss3d-003-walkthrough-720p.mp4` | 750 KB | 54.2s | 720×450 (ffmpeg 压缩) | Pro 审核附件 | ffmpeg scale |

**注意**: Pro 指出文件名 `720p` 不准确，实际分辨率是 720×450，不是标准 1280×720。

---

## 4. 测试执行记录

### 4.1 QA 命令链执行记录

#### 2026-05-03 第一次完整 QA（Pro 审核前）

| 时间 | 命令 | 结果 | 备注 |
|------|------|------|------|
| 2026-05-03 ~01:00 | `npm run qa:boss` | ✅ Passed | Desktop + mobile source-photo screenshots regenerated |
| 2026-05-03 ~01:00 | `npm run qa:models` | ✅ Passed | Live GLB turntable screenshots |
| 2026-05-03 ~01:00 | `npm run qa:candidates` | ✅ Passed | 11 candidates rendered |
| 2026-05-03 ~01:00 | `npm run check:assets` | ✅ Passed | Asset chain OK |
| 2026-05-03 ~01:00 | `npm run lint` | ✅ Passed | Clean |
| 2026-05-03 ~01:00 | `npm run build` | ✅ Passed | 1.2MB bundle, chunk size warning (expected) |
| 2026-05-03 ~01:00 | `npm run test:e2e` | ✅ Passed | 21 passed, 1 skipped |

#### 2026-05-03 第二次最小 QA（Pro 轻返修建议后，尚未执行）

Pro 建议返修后只需跑：
- `npm run qa:boss`
- `npm run check:assets`
- `npm run lint`
- `npm run build`
- （如果改交互逻辑）`npm run test:e2e`

**实际状态**: 尚未执行，等待轻返修完成。

### 4.2 Playwright 截图 QA

#### Boss Evidence Screenshots

| 文件名 | 尺寸 | uniqueColors | 生成时间 |
|--------|------|-------------|----------|
| `boss3d-20260502-desktop-source-photo.png` | 1440×960 | 72 | 2026-05-03 |
| `boss3d-20260502-mobile-source-photo.png` | 390×844 | 61 | 2026-05-03 |

#### Model QA Screenshots（已集成模型）

| 模型 | 视角 | 尺寸 | uniqueColors | 状态 |
|------|------|------|-------------|------|
| learning-tower | front | 1280×920 | - | 已生成 |
| learning-tower | side | 1280×920 | - | 已生成 |
| learning-tower | three-quarter | 1280×920 | - | 已生成 |
| storage-organizer | front | 1280×920 | - | 已生成 |
| storage-organizer | side | 1280×920 | - | 已生成 |
| storage-organizer | three-quarter | 1280×920 | - | 已生成 |

#### Candidate QA Screenshots（11 个 candidates）

每个 candidate 有 front + three-quarter 两张截图。

| Candidate | uniqueColors (front/3q) | 决策 |
|-----------|------------------------|------|
| learning-tower-white3-main-crop | - | Rejected |
| learning-tower-white8-center-crop | - | Rejected |
| learning-tower-white-rembg-nopre | - | Rejected |
| foldable-learning-tower-log-color | - | Candidate only |
| learning-tower-white-clean-source-1024 | - | Rejected |
| storage-organizer-source-crop-bright-1024 | - | QA candidate only |
| cream-wooden-play-kitchen-set-with-storage | 23 / 19 | QA-pending |
| activity-cube-baby-push-walker | 16 / 15 | QA-pending |
| crocodile-plush-rocker | 12 / 12 | QA-pending (frozen) |
| pink-unicorn-plush-rocker | 16 / 15 | QA-pending (frozen) |
| learning-tower-montessori-kitchen-tower-white-rerun-20260503 | 13 / 13 | QA-pending |

### 4.3 E2E 测试详情

**测试框架**: Playwright
**项目配置**: `playwright.config.ts`
- Desktop Chrome viewport: 1440×900
- Mobile Pixel 7 viewport: 393×852
- Web server: `npm run dev -- --host 127.0.0.1 --port 5177`
- Timeout: 60s

**测试结果**: 22 tests total
- 21 passed
- 1 skipped (`mobile defaults to simplified tour mode` on desktop project)

**测试覆盖**:
1. Renders internal 3D showroom shell (desktop + mobile)
2. Serves 2:1 showroom panorama environment (desktop + mobile)
3. Serves approved Labebe independent-site product media (desktop + mobile)
4. Serves integrated TRELLIS GLB assets for internal QA (desktop + mobile)
5. Product sheet shows real Labebe media and source evidence (desktop + mobile)
6. Canvas renders nonblank showroom pixels (desktop + mobile)
7. Opens product card from tour controls (desktop + mobile)
8. Switches between 360 panorama and studio shell (desktop + mobile)
9. Supports deterministic QA deep links for model screenshots (desktop + mobile)
10. Renders dedicated GLB QA view (desktop + mobile)
11. Mobile defaults to simplified tour mode (mobile only — skipped on desktop)

---

## 5. Playwright 视频录制记录

### 5.1 录制脚本

**脚本路径**: `scripts/record-walkthrough.mjs`

**技术栈**:
- `@playwright/test` (chromium.launch, browserContext, recordVideo)
- `child_process` (spawn dev server)
- ffmpeg (concat, scale, pad)

**录制流程**:
1. 启动 `npm run dev -- --host 127.0.0.1 --port 5177`
2. Desktop context: 1440×900 viewport, recordVideo enabled
   - 访问 `/?tour=kids-toy-storage-organizer-bookshelf-with-bins&freezeTour=1`
   - 等待 18s auto-tour
   - 访问 `/?inspect=kids-toy-storage-organizer-bookshelf-with-bins&freezeTour=1`
   - 等待 10s
3. Mobile context: 393×852 viewport, recordVideo enabled
   - 访问 `/?tour=cream-wooden-play-kitchen-set-with-storage`
   - 等待 15s auto-tour
4. ffmpeg 拼接 desktop + mobile 两段为最终 MP4

### 5.2 视频分段结构

| 时间段 | 内容 | 判断 |
|--------|------|------|
| 0.0s | 首帧基本黑屏 | ⚠️ 建议剪掉 |
| 1-3s | UI 出现，场景空白 | 可接受 |
| 4-23s | Desktop showroom 围绕 Storage Organizer | ✅ 合格 |
| 24-32s | 打开 product detail card | 内部有价值，老板版偏工程化 |
| 33-34s | Desktop→Mobile 竖屏黑边转场 | ⚠️ 需剪掉或加 title card |
| 35-39s | Mobile Play Kitchen | ✅ 合格 |
| 40-42s | Mobile Activity Cube | ✅ 合格 |
| 43-51s | Mobile Crocodile（侧面） | 正面展示不足 |
| 52-54.2s | Mobile Learning Tower（背板收尾） | ⚠️ 结尾不够干净 |

### 5.3 Pro 指出的视频问题

1. **分辨率名实不符**: 文件叫 `720p`，实际分辨率是 720×450
2. **版本号不一致**: UI 显示 `BOSS-3D-001`，包名是 `BOSS-3D-003`
3. **`Data: scraped`**: 建议改成 `Data: source-led` 或隐藏
4. **本地路径泄露**: `D:/projects/...` 可见于 product card
5. **价格显示**: `$105.99` 如果未过 product master gate，老板版需注明非 final
6. **SKU 覆盖不全**: 缺少 Pink Unicorn Plush Rocker（5/6）
7. **开头黑帧**: 0.0s 基本黑屏
8. **转场空白**: 33-34s 竖屏黑边

---

## 6. ChatGPT Pro 审核全记录

### 6.1 第一次提交（失败/不完整）

| 字段 | 值 |
|------|-----|
| **Job ID** | `bc986344090c4434986bf4bff5c891ec` |
| **提交时间** | 2026-05-03 ~14:00 |
| **Provider** | ChatGPT Pro (`pro_extended`) |
| **Model** | `gpt-5-5-pro` |
| **Attachments** | 6 个文件（review memo + OPEN_FIRST + stage5 plan + risk_note + model_qa + runbook） |
| **Drive 路径** | `toyresearch/deliverables/labebe_wonder_room_boss3d_20260502_package/` |
| **问题** | Pro 无法解析 Google Drive 媒体流；答案只生成 273 字符片段 |
| **答案状态** | provisional, reasoning 中断（"Analyzing gaps... finished=False"） |
| **最终状态** | Canceled (superseded) |
| **Cancel 原因** | Superseded by improved submission with direct media upload |

**Pro 已发出的片段**:
1. "我会按'可用于内部决策但未必可公开部署'的口径审核..."
2. "Drive evidence 已确认存在，但媒体流无法解析..."

### 6.2 第二次提交（成功/完整）

| 字段 | 值 |
|------|-----|
| **Job ID** | `75c39cf5c5d248859f8d0e46cf47731b` |
| **提交时间** | 2026-05-03 ~15:27 |
| **Provider** | ChatGPT Pro (`pro_extended`) |
| **Model** | `gpt-5-5-pro` (extended thinking effort) |
| **Attachments** | 4 个文件 |
| **Attachment 1** | `boss3d-003-walkthrough-720p.mp4` (750 KB, 720×450) |
| **Attachment 2** | `labebe-boss3d-stage5-pro-review-request.md` (3.6 KB) |
| **Attachment 3** | `BOSS_3D_003_OPEN_FIRST.md` (3.7 KB) |
| **Attachment 4** | `stage5_internal_decision_plan.md` (3.5 KB) |
| **Prompt 策略** | 明确告知这是重新提交，上一轮 Drive 媒体流无法解析，要求逐帧审核视频 |
| **完成时间** | 2026-05-03 ~15:30（约 3 分钟内完成） |
| **答案字符数** | **13,967 字符** |
| **答案状态** | final |
| **Conversation URL** | https://chatgpt.com/c/69f6f8d9-02a4-839c-9e9c-577439e8461a |

### 6.3 Pro 审核结论（第二次）

#### 总体判定

| 项目 | 判断 |
|------|------|
| Stage 5 内部决策包 | ✅ 基本通过 / 可进入内部决策 |
| Walkthrough MP4 | ✅ 内部证据通过；⚠️ 老板展示前建议轻返修 |
| 文档方向 | ✅ 大体准确 |
| Public deployment | ❌ 仍然 blocked |
| 7 个 gates | ✅ 总体准确；⚠️ Gate 4 建议改写 |

#### 必须修的 5 个问题

1. **UI `BOSS-3D-001` → `BOSS-3D-003`**
2. **README "24-second motion proof" → 54.2s walkthrough**
3. **`Data: scraped` → `Data: source-led` 或隐藏**
4. **本地路径 `D:/projects/...` 隐藏**
5. **Gate 4 表述改写**（见下方）

#### Gate 4 改写建议

**从**:
> At least one GLB passes visual QA. If no GLB passes, public version must be source-photo-only.

**改为**:
> **Public visual QA gate** — Every visual asset included in the public build must pass review. Source-photo stands must pass desktop/mobile visual review and source provenance review. No GLB may appear in the public build unless that SKU-level GLB passes silhouette, orientation, artifact, scale, material, desktop/mobile screenshot, and source-chain review. If zero GLBs pass, the public build may proceed only as source-photo-only after all other gates pass.

#### 下一步路线

1. **Step 1**: 30-60 分钟轻返修（8 项具体修改）
2. **Step 2**: 最小 QA rerun
3. **Step 3**: 冻结 Stage 5 boss package
4. **Step 4**: 进入老板决策会（4 个问题）
5. **Step 5**: 老板批准后，才开始 public gate execution

---

## 7. Google Drive 同步记录

### 7.1 同步工具配置

| 字段 | 值 |
|------|-----|
| **rclone remote** | `gdrive:` |
| **Proxy** | `127.0.0.1:7890` (mihomo/clash) |
| **Wrapper 脚本** | `~/.codex-shared/skills/gdrive-remote-check/scripts/rclone_proxy.sh` |
| **Token 有效期** | 2026-05-03 00:15 (已刷新) |

### 7.2 同步执行记录

#### 2026-05-03 第一次同步（batch 20260503 + docs）

| 字段 | 值 |
|------|-----|
| **命令** | `rclone copy ./docs gdrive:toyresearch/deliverables/labebe_wonder_room_boss3d_20260502_package/docs --progress` |
| **Transferred** | 35 files, 17.9 MiB |
| **Checks** | 67 files |
| **状态** | ✅ 成功 |

#### 2026-05-03 第二次同步（更新文档 + walkthrough）

| 字段 | 值 |
|------|-----|
| **Transferred** | 35 files, 17.9 MiB |
| **Checks** | 67 files |
| **新增文件** | stage5 plan, OPEN_FIRST, risk_note 更新, walkthrough MP4/GIF |
| **状态** | ✅ 成功 |

#### 2026-05-03 第三次同步（drive_sync_20260503_update.md）

| 字段 | 值 |
|------|-----|
| **Transferred** | 1 file, 2.46 KiB |
| **Checks** | 71 files |
| **状态** | ✅ 成功 |

---

## 8. HomePC 全量模型资产清单

> HomePC: `192.168.1.17` / `192.168.31.38`
> GPU: 2× RTX 3090 (48GB VRAM)
> 记录时间: 2026-05-03

### 8.1 Ollama 本地 LLM

Ollama 服务运行中 (`ollama serve`, PID 3071)

| # | 模型名 | ID | 大小 | 量化 | 上下文 | 能力 | 修改时间 |
|---|--------|-----|------|------|--------|------|----------|
| 1 | `nomic-embed-text:latest` | 0a109f422b47 | 274 MB | - | - | embedding | 12 days ago |
| 2 | `qwen3.5:27b` | 7653528ba5cb | 17 GB | Q4_K_M | 262K | completion, vision, tools, thinking | 2 months ago |
| 3 | `gemma3:27b` | a418f5838eaf | 17 GB | - | - | - | 13 days ago |
| 4 | `gemma3n:e4b` | 15cb39fd9394 | 7.5 GB | E4B | - | - | 13 days ago |
| 5 | `qwen3.6:35b-a3b-q4_K_M` | 07d35212591f | 23 GB | Q4_K_M | - | - | 13 days ago |

**Qwen 3.5 27B 详细参数**:
- Architecture: qwen35
- Parameters: 27.8B
- Context length: 262144
- Embedding length: 5120
- Quantization: Q4_K_M
- Requires Ollama: 0.17.1
- Default params: top_p=0.95, presence_penalty=1.5, temperature=1, top_k=20

**部署文档**: `/vol1/maint/qwen35-27b-deployment-guide.md`
- 测试时间: 2026-03-04
- 测试项目: 代码生成、Chat API、OpenAI 兼容 API、Function Calling、数学推理、中英双语
- 实测速度: ~32 tok/s
- **建议 num_ctx 限制**: 4096~32768（Ollama 默认 262K 会导致 KV cache 过大）

### 8.2 HuggingFace Hub 缓存模型

缓存路径: `~/.cache/huggingface/hub/`

| # | 模型路径 | 来源 | 用途 | 大小估计 |
|---|----------|------|------|----------|
| 1 | `models--microsoft--TRELLIS-image-large` | Microsoft | 3D 生成 (GLB) | - |
| 2 | `models--stabilityai--stable-diffusion-xl-base-1.0` | Stability AI | 图像生成 (SDXL) | - |
| 3 | `models--Lightricks--LTX-Video` | Lightricks | 视频生成 | - |
| 4 | `models--Lightricks--LTX-Video-0.9.5` | Lightricks | 视频生成 (v0.9.5) | - |
| 5 | `models--unsloth--Qwen3.6-35B-A3B-GGUF` | Unsloth | LLM inference | - |
| 6 | `models--unsloth--Qwen3-Coder-30B-A3B-Instruct-GGUF` | Unsloth | 代码生成 | - |
| 7 | `models--unsloth--Devstral-Small-2-24B-Instruct-2512-GGUF` | Unsloth | 通用推理 | - |
| 8 | `models--bartowski--Qwen_Qwen3-VL-30B-A3B-Instruct-GGUF` | Bartowski | 视觉语言模型 | - |

### 8.3 ~/models/ 目录（非 Ollama/HF 缓存）

| # | 目录名 | 大小 | 来源/说明 |
|---|--------|------|----------|
| 1 | `LTX-Video-diffusers/` | **92 GB** | LTX-Video diffusers 格式 |
| 2 | `quant-work/` | **89 GB** | 量化实验工作区 |
| 3 | `qwen36-unsloth/` | **46 GB** | Qwen 3.6 Unsloth 版本 |
| 4 | `devstral-small2/` | **38 GB** | Devstral Small 2 (24B) |
| 5 | `gemma4-awq/` | **20 GB** | Gemma 4 AWQ 量化版 |
| 6 | `ollama020/` | **19 GB** | Ollama 旧版本模型备份 |
| 7 | `qwen3-vl-bartowski/` | **18 GB** | Qwen3-VL 30B (Bartowski GGUF) |
| 8 | `qwen3-coder-unsloth/` | **18 GB** | Qwen3-Coder 30B (Unsloth) |
| 9 | `ltx-t5-textencoder/` | **18 GB** | LTX-Video T5 text encoder |
| 10 | `Qwen3.5-27B-FP8/` | **5.3 GB** | Qwen 3.5 27B FP8 量化 |
| 11 | `ollama026b/` | **28 KB** | Ollama 配置/占位 |

**~/models/ 总大小**: ~365 GB

### 8.4 ComfyUI 模型资产

ComfyUI 安装路径: `~/ComfyUI/`
模型路径: `~/ComfyUI/models/`

#### Checkpoints
| 目录/文件 | 说明 |
|-----------|------|
| `LTX-Video/` | LTX-Video 相关 checkpoints |
| `SDXL/` | Stable Diffusion XL checkpoints |

#### Diffusion Models
| 文件名 | 大小 | 说明 |
|--------|------|------|
| `ltx-video-2b-v0.9.1.safetensors` | - | LTX-Video 2B v0.9.1 |
| `ltx-video-2b-v0.9.5.safetensors` | - | LTX-Video 2B v0.9.5 |
| `ltx-video-2b-v0.9.safetensors` | - | LTX-Video 2B v0.9 |
| `wan2.1_i2v_480p_14B_fp8_e4m3fn.safetensors` | - | Wan 2.1 Image-to-Video 14B FP8 |
| `wan2.1_t2v_14B_fp8_e4m3fn.safetensors` | - | Wan 2.1 Text-to-Video 14B FP8 |

#### VAE
| 文件名 | 说明 |
|--------|------|
| `wan_2.1_vae.safetensors` | Wan 2.1 VAE |

#### Text Encoders
| 文件名 | 说明 |
|--------|------|
| `ltxv-t5xxl.safetensors` | LTX-Video T5-XXL |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | UMT5 XXL FP8 |

#### Custom Nodes
- `ComfyUI-LTXVideo`
- `ComfyUI-VideoHelperSuite`

### 8.5 TRELLIS 输入/输出资产

#### 输入目录: `~/labebe-wonder-room/trellis_inputs/`

| 目录/文件 | 说明 |
|-----------|------|
| `batch_20260503/` | 2026-05-03 batch 输入图片 |
| `kids-toy-storage-organizer-bookshelf-with-bins.jpg` | 534 KB |
| `learning-tower-montessori-kitchen-tower-white.jpg` | 345 KB |
| `rerun_20260502/` | 2026-05-02 rerun 输入 |
| `variants/` | 变体输入 |

#### 输出目录: `~/labebe-wonder-room/trellis_outputs/`

| 子目录 | 内容 |
|--------|------|
| `batch_20260503/` | 5 个新 GLB + 1 个 rerun GLB |
| `rerun_20260502/` | 2 个 clean-source GLB |
| `variants/` | 4 个 variant GLB |
| 根目录 | 2 个原始集成 GLB |

### 8.6 运行中的推理服务

| 服务 | PID | 命令 | GPU 占用 |
|------|-----|------|----------|
| Ollama | 3071 | `/usr/local/bin/ollama serve` | GPU 按需加载 |

**注意**: 实测时 `VLLM::Worker_TP*` 曾占用两张 3090，导致 GitNexus analyze 自动降级为 CPU。

---

## 9. Yoga 全量模型资产清单

> Yoga: Debian 12, 无 GPU
> 记录时间: 2026-05-03

### 9.1 GitNexus Embedding 模型

| 字段 | 值 |
|------|-----|
| **模型 ID** | `Snowflake/snowflake-arctic-embed-xs` |
| **Dimensions** | 384 |
| **框架** | Transformers.js + ONNX Runtime |
| **安装路径** | `~/.local/share/gitnexus-install/node_modules/@huggingface/transformers/.cache/Snowflake/snowflake-arctic-embed-xs` |
| **模型文件路径** | `~/.local/share/gitnexus-install/node_modules/@huggingface/transformers/models/Snowflake/snowflake-arctic-embed-xs` |
| **加载方式** | 本地 ONNX (CPU)，禁用远程下载 (`GITNEXUS_ALLOW_LOCAL_MODELS=1`, `GITNEXUS_ALLOW_REMOTE_MODELS=0`) |
| **已知问题** | MCP embedder Linux 路径硬编码先尝试 CUDA 再回退 CPU，可能 core dump |

**基准测试结果** (2026-03-07):
- 首次模型初始化: 1513ms
- 首次查询 embedding: 289ms
- RSS before init: 87MB
- RSS after init: 253MB
- analyze --embeddings 总时间: 305.2s (embedding 阶段占 287.0s)

**文档**: `/vol1/maint/docs/2026-03-07_gitnexus_embeddings_yoga_benchmark.md`

### 9.2 小智 ESP32 服务器 ASR 模型

路径: `/vol1/1000/docker/xiaozhi-esp32-server-main/models/`

| 模型 | 大小 | 说明 |
|------|------|------|
| `SenseVoiceSmall/` | 936 MB (`model.pt`) | ASR 语音识别模型 |
| `wav2vec2-base-960h.pt` | 0 bytes (空文件) | wav2vec2 占位 |

### 9.3 FunASR 模型（StoryPlay 项目）

路径: `/vol1/1000/projects/storyplay/.venv-funasr` 和 `/vol1/1000/projects/storyplay/tmp/funasr_models`

### 9.4 Playwright Chromium

| 版本 | 路径 | 状态 |
|------|------|------|
| chromium-1200 | `~/.cache/ms-playwright/chromium-1200/` | 预装，完整 |
| chromium-1217 | `~/.cache/ms-playwright/chromium-1217/` | 手动下载，dirty symlink |
| chromium_headless_shell-1200 | `~/.cache/ms-playwright/chromium_headless_shell-1200/` | 预装，完整 |
| chromium_headless_shell-1217 | `~/.cache/ms-playwright/chromium_headless_shell-1217/` | symlink → 1200 |

---

## 10. Maint 库大模型研究文档索引

> 以下文档位于 `/vol1/maint/docs/`，记录了对各种大模型的研究、部署、测试和决策过程。

| # | 文档名 | 日期 | 核心内容 |
|---|--------|------|----------|
| 1 | `qwen35-27b-deployment-guide.md` | 2026-03-04 | Qwen 3.5 27B 完整部署方案（Ollama + 双 3090）。含实机测试：代码生成、Chat API、OpenAI 兼容 API、Function Calling、数学推理、中英双语。速度 ~32 tok/s。 |
| 2 | `2026-03-02_model_and_key_inventory.md` | 2026-03-02 | 模型路由架构全览：LLMConnector 主通道（DashScope + MiniMax）、ModelRouter 三源融合、Web 提供方（ChatGPT Pro / Gemini / Qwen）、额度探测与 Fallback 策略、API Key 全量清单。 |
| 3 | `2026-03-02_full_maintenance_session.md` | 2026-03-02 | 全面维护记录：系统健康诊断、文档体系更新、模型配置审计、额度轮询调频、CcExecutor PTY 死锁修复。 |
| 4 | `2026-03-02_routing_matrix_deep_research.md` | 2026-03-02 | LLM 路由矩阵深度研究。 |
| 5 | `2026-03-02_quota_optimization_revised.md` | 2026-03-02 | 额度优化修订版。 |
| 6 | `2026-03-02_chatgptrest_codebase_snapshot.md` | 2026-03-02 | ChatgptREST 代码库快照。 |
| 7 | `2026-03-02_routing_thinking_extended.md` | 2026-03-02 | Thinking Extended 路由研究。 |
| 8 | `2026-03-07_gitnexus_embeddings_yoga_benchmark.md` | 2026-03-07 | GitNexus Embedding 在 Yoga 上的基准测试：模型 `Snowflake/snowflake-arctic-embed-xs` (384 dims)，CPU-only，analyze --embeddings 305.2s，MCP CUDA-first core dump 风险。 |
| 9 | `2026-03-07_gitnexus_homepc_priority_local_mcp.md` | 2026-03-07 | HomePC 优先承担重型 analyze --embeddings，Yoga 作为 query/MCP host。本地模型复用策略、`Snowflake/snowflake-arctic-embed-xs` 同步到 HomePC。 |
| 10 | `2026-03-07_homepc_funasr_ffmpeg_validation.md` | 2026-03-07 | HomePC FunASR + FFmpeg 验证。 |
| 11 | `2026-03-07_chatgptrest_evomap_runtime_verification.md` | 2026-03-07 | ChatgptREST EvoMap 运行时验证。 |
| 12 | `2026-03-07_maint_machine_context_evomap_ingestion.md` | 2026-03-07 | Maint 机器上下文 EvoMap 摄入。 |
| 13 | `2026-03-07_chatgptrest_evomap_ingestion_audit_and_refine_plan.md` | 2026-03-07 | ChatgptREST EvoMap 摄入审计。 |
| 14 | `2026-03-07_evomap_agent_evolution_ingestion_plan.md` | 2026-03-07 | EvoMap Agent 进化摄入计划。 |
| 15 | `2026-03-07_maint_layer_inventory.md` | 2026-03-07 | Maint 层资产清单。 |
| 16 | `2026-03-06_agent_instruction_skill_workflow_inventory.md` | 2026-03-06 | Agent 指令/技能/工作流清单。 |
| 17 | `2026-03-06_homepc_backup_relayout_plan.md` | 2026-03-06 | HomePC 备份重排计划。 |
| 18 | `个人 AI 投资助理生态深度研究报告.md` | - | 个人 AI 投资助理生态研究。 |
| 19 | `架构顾问意见.md` | - | 架构顾问意见汇总。 |
| 20 | `概念讲解与应用.md` | - | 概念讲解与应用。 |

### 10.1 外部 API 模型路由（当前活跃）

| Provider | 模型 | 状态 | 用途 |
|----------|------|------|------|
| DashScope (通义) | `qwen3-coder-plus` | ✅ 活跃 | Coding |
| DashScope (通义) | `qwen3.5-plus` | ✅ 活跃 | 通用 |
| DashScope (通义) | `MiniMax-M2.5` | ✅ 活跃 | 通用/Review/Planning |
| DashScope (通义) | `kimi-k2.5` | ✅ 活跃 | 编码/Debug |
| DashScope (通义) | `glm-5` | ✅ 活跃 | 备选 |
| MiniMax (Anthropic) | `MiniMax-M2.5` | ✅ 活跃 | 兜底 fallback |
| ChatGPT Pro (web) | `gpt-5-5-pro` | ✅ 活跃 | 深度审核/Review |
| Gemini (web) | `gemini-2.5-pro` | ✅ 活跃 | 深度研究 |
| OpenAI API | `gpt-5-mini` | ❌ 禁用 | 额度探测 |
| Gemini API | `gemini-2.5-pro` | ❌ 禁用 | 额度探测 |

---

## 11. 结论与决策索引

### 11.1 GLB 策略决策（Pro 确认）

| SKU | 策略 | 状态 |
|-----|------|------|
| Storage Organizer | 最强内部 3D QA hero；source-photo 默认 | ✅ 保持 |
| Play Kitchen | 优先人工视觉审查；硬表面可投 GLB | ⏳ 待审查 |
| Activity Cube | 第二优先审查 | ⏳ 待审查 |
| Learning Tower | 停止盲目 rerun；只跑一次 clean isolated source | ⏳ 待准备 clean source |
| Crocodile Plush Rocker | 冻结 TRELLIS；source-photo 默认 | ❄️ Frozen |
| Pink Unicorn Plush Rocker | 冻结 TRELLIS；source-photo 默认 | ❄️ Frozen |

### 11.2 Stage 5 定义（Pro 确认）

- Stage 5 = internal decision-ready boss presentation package
- **不是 public deployment**
- Boss-facing = source-photo-led
- GLB = QA-only
- Public blocked until 7 gates complete

### 11.3 7 个 Public Deployment Gates

1. Source provenance gate
2. Canonical product master gate
3. Claim inventory gate
4. **Public visual QA gate**（建议改写）
5. Public technical smoke gate
6. Amazon exclusion audit
7. Compliance and business sign-off

### 11.4 机器分工（Pro 确认）

| 机器 | 角色 | 任务 |
|------|------|------|
| Yoga | Web/build/QA/package/sync | QA、lint、build、文档、Drive sync |
| HomePC | Targeted TRELLIS only | 最多 3 个定向 GLB（Play Kitchen、Activity Cube、Learning Tower clean source） |
| Windows 笔记本 | 视觉审查/录屏/剪辑 | 人工对比、walkthrough capture、Stage 5 package |

### 11.5 HomePC 模型资产总结

| 类别 | 数量 | 总大小估计 |
|------|------|-----------|
| Ollama LLM | 5 个 | ~64.8 GB |
| HuggingFace Hub 缓存 | 8 个模型 | - |
| ~/models/ 目录 | 11 个 | ~365 GB |
| ComfyUI 模型 | 8+ 个文件 | - |
| TRELLIS 输出 GLB | 13 个 | ~21 MB |
| **合计** | - | **~430+ GB** |

---

## 12. 已知缺陷与 TODO

### 12.1 高优先级（Pro 要求轻返修）

- [ ] UI `BOSS-3D-001` → `BOSS-3D-003`
- [ ] README "24s motion proof" → "54.2s walkthrough"
- [ ] `Data: scraped` → `Data: source-led` / 隐藏
- [ ] 隐藏本地路径 `D:/projects/...`
- [ ] 视频重录/重导出为真正 1280×720
- [ ] 剪掉开头黑帧 + 33-34s 空白转场
- [ ] 结尾加 1-2s 稳定收尾
- [ ] 如需 6 SKU 全覆盖，补录 Pink Unicorn
- [ ] Gate 4 表述改写

### 12.2 中优先级

- [ ] Boss demo script 独立文件（当前嵌在 README 中）
- [ ] Claim inventory summary（不只是 gate map）
- [ ] 抽查 risk_note、model_qa_report、runbook 实际内容

### 12.3 低优先级/技术债

- [ ] Playwright chromium-1217 为 dirty symlink 安装，升级时可能再次出问题
- [ ] HomePC canonical LAN `192.168.31.38` 不可达，只能走 legacy `192.168.1.17`
- [ ] `qa:candidates` 首次运行 180s 超时，需调整脚本 timeout
- [ ] ChatgptREST `chatgptrest.env` 应增加 `NO_PROXY` 白名单
- [ ] GitNexus MCP embedder Linux CUDA-first core dump 风险（上游缺陷）
- [ ] Ollama `qwen3.5:27b` 默认 context 262K 过大，建议限制为 4096~32768
- [ ] HomePC `~/models/` 目录中部分模型可能重复（如 qwen36-unsloth 46GB vs ollama qwen3.6 23GB）

---

## 附录：所有相关文档索引

| 文档 | 路径 | 内容 |
|------|------|------|
| 本执行日志 | `docs/AI_TOOLS_AND_MODELS_EXECUTION_LOG.md` | 全记录 |
| 代理避坑指南 | `docs/AGENT_PROXY_TRAPS_AND_BEST_PRACTICES.md` | 代理策略 |
| Stage 5 决策计划 | `docs/stage5_internal_decision_plan.md` | Stage 5 定义、gates |
| Open-first README | `docs/BOSS_3D_003_OPEN_FIRST.md` | 老板入口文档 |
| 风险笔记 | `docs/BOSS_3D_003_risk_note.md` | Blockers、checklist |
| 模型 QA 报告 | `docs/asset_pipeline/model_qa_report_20260502.md` | SKU strategy |
| 执行手册 | `docs/asset_pipeline/boss3d_chain_runbook_20260502.md` | 资源分配 |
| 资产清单 | `docs/asset_pipeline/showroom_asset_manifest.json` | GLB、panorama、source |
| Drive 同步日志 | `docs/drive_sync_20260503.md` / `drive_sync_20260503_update.md` | 同步记录 |
| Pro 审核答案 | `/tmp/pro-answer-v2.md` | 13,967 字符完整答案 |
| Pro 审核请求 | `/tmp/labebe-boss3d-stage5-pro-review-request.md` | 请求 memo |
| QA 录制脚本 | `scripts/record-walkthrough.mjs` | Playwright 视频录制 |
| Drive 代理 wrapper | `~/.codex-shared/skills/gdrive-remote-check/scripts/rclone_proxy.sh` | rclone 代理 |
| **Maint: Qwen 部署** | `/vol1/maint/qwen35-27b-deployment-guide.md` | Qwen 3.5 27B 部署指南 |
| **Maint: 模型路由** | `/vol1/maint/docs/2026-03-02_model_and_key_inventory.md` | 全量模型路由 |
| **Maint: GitNexus 基准** | `/vol1/maint/docs/2026-03-07_gitnexus_embeddings_yoga_benchmark.md` | Embedding 测试 |
| **Maint: HomePC MCP** | `/vol1/maint/docs/2026-03-07_gitnexus_homepc_priority_local_mcp.md` | HomePC 分析策略 |
| **Maint: 全面维护** | `/vol1/maint/docs/2026-03-02_full_maintenance_session.md` | 系统维护记录 |
