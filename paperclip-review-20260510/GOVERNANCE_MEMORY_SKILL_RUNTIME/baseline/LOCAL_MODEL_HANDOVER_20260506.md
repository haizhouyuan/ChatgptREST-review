# HomePC / Yoga 本地模型与基础设施交接文档

> 生成日期: 2026-05-06
> 实地探查日期: 2026-05-06
> 探查方式: SSH 到 HomePC (`192.168.1.17`) + Yoga 本地检查
> 原则: **文档记录仅供参考，以实地探查结果为准**

---

## 执行摘要

**当前本地模型主力**: Ollama 0.17.5 stable lane（qwen3.6 综合最强 + qwen3.5 结构化最稳 + gemma3/gemma3n 预处理快道）。Gemma4 系列和 vLLM 曾经实验过但当前 **drifted**（未保持 live）。ComfyUI 在 GPU0 常驻运行（Wan 2.1 benchmark 刚完成）。TRELLIS pipeline 就绪但当前空闲。

**最大发现**: ComfyUI LTX 模型资产达 **~151GB**（14+ 个 checkpoint），远超之前记录的 3 个；Wan 2.1 T2V 36/36 benchmark 已完成（~549s/clip）。

---

## 一、机器基线（实地验证）

### 1.1 HomePC

| 项目 | 文档记录 | 实地验证 | 差异 |
|------|----------|----------|------|
| Hostname | `yuanhaizhou-home` | `yuanhaizhou-home` | ✅ 一致 |
| OS | Ubuntu 22.04 | Ubuntu 22.04.5 LTS | ✅ 一致 |
| Kernel | `6.8.0-107-generic` | `6.8.0-110-generic` | ⚠️ 已升级 |
| CPU | Ryzen 7 9700X | Ryzen 7 9700X | ✅ 一致 |
| RAM | 60GB | — | — |
| GPU | 2× RTX 3090 24GB | 2× RTX 3090 24GB, Driver 535.288.01 | ✅ 一致 |
| CUDA (driver) | 12.2 | 12.2 | ✅ 一致 |
| CUDA (nvcc) | 11.8 | 11.8 (V11.8.89) | ✅ 一致 |
| CUDA_HOME | — | **未设置** | ⚠️ 需补 |
| 可用 SSH | `192.168.1.17` | `192.168.1.17` | ✅ 一致 |
| 网卡真实 IP | `192.168.31.38` | `192.168.31.38` | ✅ 一致 |
| Home 分区 | ~1.2TB | 1.7TB total, 835G used, 834G free | ✅ 充足 |

### 1.2 Yoga

| 项目 | 状态 |
|------|------|
| OS | Debian 12 |
| GPU | 无 |
| GitNexus | `~/.local/share/gitnexus-install/` 存在（ snowflake-arctic-embed-xs CPU ONNX） |
| FunASR/SenseVoice | `/vol1/1000/docker/xiaozhi-esp32-server-main/models/SenseVoiceSmall/` 936MB |
| OpenClaw | `~/.config/openclaw/` **不存在**（HomePC 上也不存在） |

---

## 二、当前 Live 模型服务

### 2.1 Ollama（主 LLM 后端）

**状态**: ✅ 运行中（PID 3071, `127.0.0.1:11434`）
**版本**: 0.17.5
**配置路径**: `/usr/local/bin/ollama`
**模型存储**: `/REDACTED_HOME/.ollama/models/`

| 模型名 | 大小 | 参数量 | 量化 | Capabilities | Tool Calling | 角色定位 |
|--------|------|--------|------|-------------|--------------|----------|
| `qwen3.5:27b` | 17 GB | 27.8B | Q4_K_M | completion, vision, **tools**, thinking | ✅ 已验证 | 结构化最稳 / tool lane |
| `qwen3.6:35b-a3b-q4_K_M` | 23 GB | 36.0B | Q4_K_M | completion, vision, **tools**, thinking | ✅ 已验证 | 综合最强 / 速度领先 |
| `gemma3:27b` | 17 GB | 27.4B | Q4_K_M | completion, vision | ❌ 不支持 | 中型摘要 / 预处理 |
| `gemma3n:e4b` | 7.5 GB | 6.9B | Q4_K_M | completion | ❌ 不支持 | 轻量草拟 / 低延迟 |
| `nomic-embed-text:latest` | 274 MB | — | — | embedding | N/A | 本地 embedding |

**关键验证**（2026-05-06 实地 `ollama show`）：
- qwen3.5 和 qwen3.6 都通过 Ollama API 报告 `tools` 能力
- 文档记录中已通过 `/v1/chat/completions` 验证返回 `tool_calls`
- gemma3/gemma3n 的 tool-calling probe 返回 HTTP 400（不支持）

**注意**: 之前报告中的 "qwen3.6 thinking trap" 结论**需修正**。`thinking` 是模型原生 capability，不是 bug。之前的问题出现在特定调用模式（如 `think=true`），而非模型本身缺陷。

### 2.2 ComfyUI（视频生成）

**状态**: ✅ 运行中（PID 38935, `127.0.0.1:8188`）
**安装路径**: `/REDACTED_HOME/ComfyUI/`
**模型根**: `/REDACTED_HOME/ComfyUI/models/`
**当前 GPU**: GPU 0 占用 15.8GB（Wan 2.1 相关）

**Diffusion Models** (`/REDACTED_HOME/ComfyUI/models/diffusion_models/`):

| 文件 | 大小 | 说明 |
|------|------|------|
| `ltx-video-2b-v0.9.1.safetensors` | symlink → checkpoints/LTX-Video | LTX 2B v0.9.1 |
| `ltx-video-2b-v0.9.5.safetensors` | symlink → checkpoints/LTX-Video | LTX 2B v0.9.5 |
| `ltx-video-2b-v0.9.safetensors` | symlink → checkpoints/LTX-Video | LTX 2B v0.9 |
| `wan2.1_i2v_480p_14B_fp8_e4m3fn.safetensors` | **16 GB** | Wan 2.1 I2V 14B FP8 |
| `wan2.1_t2v_14B_fp8_e4m3fn.safetensors` | **14 GB** | Wan 2.1 T2V 14B FP8 |

**Text Encoders** (`/REDACTED_HOME/ComfyUI/models/text_encoders/`):

| 文件 | 大小 | 说明 |
|------|------|------|
| `ltxv-t5xxl.safetensors` | 18 GB | LTX T5-XXL（转换后 bare-key） |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | 6.3 GB | UMT5 XXL FP8（Wan 2.1 用） |

**VAE** (`/REDACTED_HOME/ComfyUI/models/vae/`):

| 文件 | 大小 | 说明 |
|------|------|------|
| `wan_2.1_vae.safetensors` | 243 MB | Wan 2.1 VAE |

**Checkpoints** (`/REDACTED_HOME/ComfyUI/models/checkpoints/LTX-Video/`):

> ⚠️ **重大发现**: 该目录实际包含 **~151GB** 模型资产（14+ 文件），远超之前记录的 3 个：

| 文件 | 大小 | 说明 |
|------|------|------|
| `ltxv-13b-0.9.7-dev.safetensors` | 27 GB | LTX 13B dev v0.9.7 |
| `ltxv-13b-0.9.7-dev-fp8.safetensors` | 15 GB | LTX 13B dev FP8 v0.9.7 |
| `ltxv-13b-0.9.7-distilled.safetensors` | 27 GB | LTX 13B distilled v0.9.7 |
| `ltxv-13b-0.9.7-distilled-fp8.safetensors` | 15 GB | LTX 13B distilled FP8 v0.9.7 |
| `ltxv-13b-0.9.7-distilled-lora128.safetensors` | 1.3 GB | LTX 13B distilled LoRA |
| `ltxv-13b-0.9.8-dev-fp8.safetensors` | 15 GB | LTX 13B dev FP8 v0.9.8 |
| `ltxv-13b-0.9.8-distilled-fp8.safetensors` | 15 GB | LTX 13B distilled FP8 v0.9.8 |
| `ltxv-2b-0.9.6-dev-04-25.safetensors` | 6.0 GB | LTX 2B dev |
| `ltxv-2b-0.9.6-distilled-04-25.safetensors` | 6.0 GB | LTX 2B distilled |
| `ltxv-2b-0.9.8-distilled-fp8.safetensors` | 4.2 GB | LTX 2B distilled FP8 |
| `ltx-video-2b-v0.9.1.safetensors` | 5.4 GB | LTX 2B v0.9.1 |
| `ltx-video-2b-v0.9.5.safetensors` | 6.0 GB | LTX 2B v0.9.5 |
| `ltx-video-2b-v0.9.safetensors` | 8.8 GB | LTX 2B v0.9 |
| `ltxv-spatial-upscaler-0.9.7.safetensors` | 482 MB | 空间超分 |
| `ltxv-spatial-upscaler-0.9.8.safetensors` | 482 MB | 空间超分 |
| `ltxv-temporal-upscaler-0.9.7.safetensors` | 500 MB | 时序超分 |
| `ltxv-temporal-upscaler-0.9.8.safetensors` | 500 MB | 时序超分 |

**Wan 2.1 Benchmark 状态**:
- T2V 36/36 已完成（2026-05-01 启动）
- 平均耗时: **549.6s** (~9.1 分钟/clip)
- 日志: `/tmp/wan_t2v_status.log`, `/tmp/wan_t2v_benchmark_u.log`, `/tmp/ad_progress.log`

### 2.3 TRELLIS（3D GLB 生成）

**状态**: ⏸️ Pipeline 就绪，当前空闲
**Conda env**: `trellis` (`/REDACTED_HOME/miniconda3/envs/trellis`)
**生成脚本**: `/REDACTED_HOME/trellis_generate.py`
**模型**: `microsoft/TRELLIS-image-large` (HF Hub 缓存)
**输入**: `/REDACTED_HOME/labebe-wonder-room/trellis_inputs/`
**输出**: `/REDACTED_HOME/labebe-wonder-room/trellis_outputs/`
**GPU**: 偏好 GPU 1（GPU 0 常驻 ComfyUI）

---

## 三、曾经实验过但当前 Drifted 的服务

> 以下服务在文档中有记录，但当前实地探查确认 **未运行**。

### 3.1 vLLM（双卡 LLM 推理）

**文档记录**: Qwen3.5-27B-FP8 + vLLM TP=2，端口 8000
**实地状态**: ❌ 无进程，端口 8000 未监听
**阻塞**: vLLM tunnel 已漂移，需重新配置
**模型文件**: `/REDACTED_HOME/models/Qwen3.5-27B-FP8/` (5.3 GB)

### 3.2 llama-server（Qwen3.6 GGUF）

**文档记录**: 通过 llama-server 提供 OpenAI 兼容 API，端口 8080
**实地状态**: ❌ 无进程，端口 8080 未监听
**模型文件**: `/REDACTED_HOME/models/qwen36-unsloth/Qwen3.6-35B-A3B-UD-Q5_K_M.gguf`
**注意**: 文档建议用 llama-server 替代 Ollama 以避免 thinking trap，但当前 Ollama 0.17.5 已能正确处理 qwen3.6

### 3.3 Gemma4 实验（Ollama 0.20.3）

**文档记录**: 曾通过独立 Ollama 0.20.3 实例在端口 11435/11436 运行
**实地状态**: ❌ 端口未监听，`/tmp/ollama-new/` 目录已不存在
**模型文件**: `/REDACTED_HOME/models/quant-work/` 下的 GGUF 文件

**Gemma4 31B lane** (11435):
- 模型: `gemma4:31b` (Q4_K_M / Q8_0 / BF16)
- 显存: ~19GB
- 结论: Q4_K_M 可用，TurboQuant 权重量化失败

**Gemma4 26B-A4B lane** (11436):
- 模型: `gemma4:26b-a4b-it-q4_K_M` (UD-Q4_K_M)
- 显存: ~15-18GB
- 结论: 不是全局替代 31B，特定摘要场景更快

**TurboQuant 实验结论**:
| 测试 | 结果 |
|------|------|
| Gemma4 31B BF16→TQ1_0 (CPU/GPU) | ❌ 乱码，权重量化失败 |
| Gemma4 31B BF16→TQ2_0 (CPU/GPU) | ❌ 乱码，权重量化失败 |
| **唯一科研方向** | 正常权重 + 非对称 KV cache（`-ctk q8_0 -ctv turbo4`，未做） |

---

## 四、模型资产完整清单

### 4.1 Ollama 管理模型 (`/REDACTED_HOME/.ollama/models/`)

| 模型 | 大小 | 状态 |
|------|------|------|
| `nomic-embed-text:latest` | 274 MB | ✅ live |
| `qwen3.5:27b` | 17 GB | ✅ live |
| `qwen3.6:35b-a3b-q4_K_M` | 23 GB | ✅ live |
| `gemma3:27b` | 17 GB | ✅ live |
| `gemma3n:e4b` | 7.5 GB | ✅ live |
| **小计** | **~64.8 GB** | |

### 4.2 ~/models/ 独立目录 (`/REDACTED_HOME/models/`)

| 目录 | 大小 | 说明 | 状态 |
|------|------|------|------|
| `LTX-Video-diffusers/` | ~92 GB | LTX diffusers 格式 | ✅ 存在 |
| `quant-work/` | ~73 GB | 量化实验（含 Gemma4 TurboQuant 产物） | ✅ 存在 |
| `qwen36-unsloth/` | ~46 GB | Qwen 3.6 Unsloth GGUF | ✅ 存在 |
| `devstral-small2/` | ~38 GB | Devstral Small 2 24B | ✅ 存在 |
| `gemma4-awq/` | ~20 GB | Gemma 4 AWQ 量化版 | ✅ 存在 |
| `ollama020/` | ~19 GB | Ollama 旧版本模型备份 | ✅ 存在 |
| `qwen3-vl-bartowski/` | ~18 GB | Qwen3-VL 30B (Bartowski GGUF) | ✅ 存在 |
| `qwen3-coder-unsloth/` | ~18 GB | Qwen3-Coder 30B (Unsloth GGUF) | ✅ 存在 |
| `ltx-t5-textencoder/` | ~18 GB | LTX T5 text encoder (diffusers) | ✅ 存在 |
| `Qwen3.5-27B-FP8/` | ~5.3 GB | Qwen 3.5 27B FP8 (vLLM 候选) | ✅ 存在 |
| `ollama026b/` | 28 KB | Ollama 配置占位 | ✅ 存在 |
| **小计** | **~365+ GB** | | |

### 4.3 quant-work/ 详细 (`/REDACTED_HOME/models/quant-work/`)

| 文件 | 大小 | 说明 |
|------|------|------|
| `gemma4-31b-bf16.gguf` | 58 GB | Gemma4 31B BF16 原始权重 |
| `gemma4-31b-tq1_0.gguf` | 6.9 GB | TurboQuant TQ1_0 权重量化 — **已证伪（乱码）** |
| `gemma4-31b-tq2_0.gguf` | 8.2 GB | TurboQuant TQ2_0 权重量化 — **已证伪（乱码）** |
| `ollama-new-models/` | — | Gemma4 实验用的 Ollama 0.20.3 模型存储（blobs + manifests） |

### 4.4 HuggingFace Hub 缓存 (`/REDACTED_HOME/.cache/huggingface/hub/`)

| 模型路径 | 来源 | 用途 |
|----------|------|------|
| `models--microsoft--TRELLIS-image-large` | Microsoft | 3D GLB 生成 |
| `models--stabilityai--stable-diffusion-xl-base-1.0` | Stability AI | 图像生成 |
| `models--Lightricks--LTX-Video` | Lightricks | 视频生成 |
| `models--Lightricks--LTX-Video-0.9.5` | Lightricks | 视频生成 v0.9.5 |
| `models--unsloth--Qwen3.6-35B-A3B-GGUF` | Unsloth | LLM inference |
| `models--unsloth--Qwen3-Coder-30B-A3B-Instruct-GGUF` | Unsloth | 代码生成 |
| `models--unsloth--Devstral-Small-2-24B-Instruct-2512-GGUF` | Unsloth | 通用推理 |
| `models--bartowski--Qwen_Qwen3-VL-30B-A3B-Instruct-GGUF` | Bartowski | 视觉语言模型 |

### 4.5 ComfyUI 模型资产汇总

| 类别 | 路径 | 估算大小 |
|------|------|----------|
| Checkpoints (LTX-Video) | `/REDACTED_HOME/ComfyUI/models/checkpoints/LTX-Video/` | ~151 GB |
| Diffusion Models | `/REDACTED_HOME/ComfyUI/models/diffusion_models/` | symlink → checkpoints |
| Text Encoders | `/REDACTED_HOME/ComfyUI/models/text_encoders/` | ~25 GB |
| VAE | `/REDACTED_HOME/ComfyUI/models/vae/` | ~243 MB |
| Wan 2.1 (diffusion_models) | `/REDACTED_HOME/ComfyUI/models/diffusion_models/wan2.1_*` | ~30 GB |

### 4.6 总体资产规模

| 类别 | 大小 |
|------|------|
| Ollama 模型 | ~65 GB |
| ~/models/ 独立目录 | ~365+ GB |
| ComfyUI checkpoints (LTX) | ~151 GB |
| ComfyUI text_encoders + Wan | ~55 GB |
| HF Hub 缓存 | — |
| TRELLIS 输出 GLB | ~21 MB |
| **合计** | **~640+ GB** |

---

## 五、实验结论（文档 vs 实地交叉验证）

### 5.1 Ollama Stable Lane Benchmark（已验证）

**短输入** (`num_ctx=8192, num_predict=256`):

| 模型 | 结构化抽取 | Repo 推理 | Tool 支持 |
|------|-----------|-----------|-----------|
| qwen3.5:27b | 6.1s | 7.5s | ✅ |
| qwen3.6:35b | 4.8s | 2.8s | ✅ |
| gemma3:27b | 4.9s | 5.1s | ❌ |
| gemma3n:e4b | 2.7s | 2.5s | ❌ |

**长输入** (`num_ctx=8192, num_predict=384`):

| 模型 | 长摘要 (5K) | 长 JSON (5K) |
|------|-------------|--------------|
| qwen3.5:27b | 26.9s | 13.5s |
| qwen3.6:35b | 6.9s* | 5.2s |
| gemma3:27b | 13.4s | 9.2s |
| gemma3n:e4b | 4.8s | 3.6s |

\* qwen3.6 长摘要命中过 `done_reason=length`，建议增大 `num_predict`

### 5.2 Flash Attention（qwen3.5 lane）

| 任务 | Baseline | Flash Attention | 提升 |
|------|----------|-----------------|------|
| JSON 抽取 | 6.115s | 5.574s | **+8.85%** |
| 风险总结 | 7.462s | 6.946s | **+6.92%** |

结论: 中小幅收益，非数量级跃迁。

### 5.3 Gemma4 31B vs 26B-A4B A/B

**短 prompt**: 26B 慢约 50%（~9900ms vs ~6500ms）
**长输入**: 各有优势场景
- 26B 胜: planning_summary_5k (+16%), planning_comprehensive_12k (+18%)
- 31B 胜: planning_risk_5k (+79%), finbot_earnings_8k (+38%)

结论: 26B 不是全局替代，是特定场景补充 lane。

### 5.4 Tool Calling 验证

| 模型 | Ollama API show | /v1/chat/completions 实测 |
|------|-----------------|---------------------------|
| qwen3.5:27b | reports `tools` | ✅ 返回 `tool_calls` |
| qwen3.6:35b | reports `tools` | ✅ 返回 `tool_calls` |
| gemma3:27b | 无 `tools` | ❌ HTTP 400 |
| gemma3n:e4b | 无 `tools` | ❌ HTTP 400 |

### 5.5 长上下文 Needle 测试

- 400K 字符中命中 `NEEDLE_CODE_824713`
- 耗时: **238.6s**
- 结论: 能力存在但速度偏慢，不适合交互式高频长文问答

### 5.6 强结构化长文抽取

- 10.8K 字符 planning 材料包 JSON schema 抽取
- 当前 Q4_K_M + Ollama 基线: **明显偏慢，交互体验不理想**
- 结论: 适合后台批处理 / first pass digest，不适合交互式强结构化 lane

---

## 六、研究计划与下一步

### 6.1 高优先级（P0）

| # | 任务 | 阻塞 | 预期工作量 |
|---|------|------|-----------|
| 1 | **OpenClaw 接入 HomePC Ollama** | OpenClaw 当前无本地 provider 配置 | 中等 |
| 2 | **vLLM 双卡 lane 恢复** | vLLM :8000 tunnel 已漂移，需重新配置 | 较大 |
| 3 | **Runtime Allocator 从 YAML 加载** | `allocator_mvp.py` 仍是硬编码 | 中等 |
| 4 | **Ollama context 限制 262K → 32K** | 默认 262K 导致 KV cache 过大 | 小 |
| 5 | **ollama_gpu0 profile 更新** | 当前写 `qwen2.5:32b`，实际部署 `qwen3.5:27b` | 小 |

### 6.2 中优先级

| # | 任务 | 说明 |
|---|------|------|
| 6 | GitNexus Embedding 迁移到 HomePC GPU | Yoga CPU 305s 太慢；MCP CUDA-first core dump |
| 7 | llama-server 配置为 systemd service | 提供稳定本地 LLM 后端（端口 8080） |
| 8 | TurboQuant 非对称 KV cache 实验 | 正常权重 + `-ctk q8_0 -ctv turbo4`，唯一未证伪方向 |
| 9 | HomePC ~/models/ 重复清理 | qwen36-unsloth 46GB vs Ollama qwen3.6 23GB |
| 10 | qwen3-coder:30b-a3b 专用 lane 部署 | 代码 lane，优先级高 |
| 11 | Qwen3.5-27B-FP8 + vLLM TP=2 综合 lane | 本地最强综合 lane |
| 12 | Devstral Small 2 通用推理 lane | 24B，~/models/devstral-small2/ 已就绪 |

### 6.3 低优先级 / 探索性

| # | 任务 | 说明 |
|---|------|------|
| 13 | Qwen3-VL 多模态 OCR lane | ~/models/qwen3-vl-bartowski/ 已就绪 |
| 14 | Wan 2.1 5B 测试 | 14B 已跑通，测试 5B 版本 |
| 15 | LTX-Video 2.3 评估 | 需 Python ≥3.12, CUDA >12.7, PyTorch ~2.7 |
| 16 | MiniMind 实际训练跑通 | 代码就绪，未实际运行 |
| 17 | Gemma4 31B 重新评估 | TurboQuant 失败后，Q4_K_M/Q8_0 是否值得保留 |

---

## 七、关键文档路径索引（绝对路径）

### 核心交接文档

| 文档 | 路径 | 内容 |
|------|------|------|
| **本交接文档** | `/vol1/1000/projects/toyresearch/docs/LOCAL_MODEL_HANDOVER_20260506.md` | 最新实地验证结果 |
| 本地模型研究清单 | `/vol1/1000/projects/toyresearch/docs/LOCAL_MODEL_RESEARCH_INVENTORY.md` | 上一轮汇总（有遗漏） |
| AI 工具与模型执行日志 | `/vol1/1000/projects/toyresearch/docs/AI_TOOLS_AND_MODELS_EXECUTION_LOG.md` | 全量执行记录 (815 行) |

### HomePC 部署与评估文档

| 文档 | 路径 | 内容 |
|------|------|------|
| HomePC 本地模型部署评估 | `/vol1/maint/docs/2026-04-04_homepc_local_model_deployment_and_project_routing_assessment.md` | OpenClaw 接入判断、4 条 lane 架构 |
| TurboQuant/Flash 实验档案 | `/vol1/maint/docs/2026-04-20_homepc_local_model_turboquant_flash_experiment_dossier.md` | 完整实验矩阵、A/B 结果 |
| LLM 与多媒体验证计划 | `/vol1/maint/docs/llm测试20260429.md` | 最新测试计划、Pro 调研结论 |
| Qwen 3.5 27B 部署指南 | `/vol1/maint/qwen35-27b-deployment-guide.md` | 实机测试记录、API 验证 |

### Runtime / 路由设计文档

| 文档 | 路径 | 内容 |
|------|------|------|
| Runtime Allocator 设计 | `/vol1/1000/projects/toyresearch/docs/RUNTIME_ALLOCATOR_DESIGN.md` | 4 providers、fallback、熔断 |
| Runtime 画像 | `/vol1/1000/projects/toyresearch/runtime_allocator/profiles/runtime_profiles.yaml` | ollama_gpu0/gemini_local 静态能力 |
| 路由策略 | `/vol1/1000/projects/toyresearch/runtime_allocator/profiles/routing_policy.yaml` | 36 个 task-class fallback chain |
| P0 交接 | `/vol1/1000/projects/toyresearch/P0_HANDOVER.md` | allocator/orchestrator 完成状态 |

### Skill 文档

| 文档 | 路径 | 内容 |
|------|------|------|
| HomePC 视频管道 | `/vol1/1000/projects/toyresearch/skills/homepc-video-pipeline/SKILL.md` | LTX/ComfyUI/llama-server 完整指南 |
| HomePC 工作站桥接 | `/vol1/1000/projects/toyresearch/skills/homepc-workstation-bridge/SKILL.md` | TRELLIS SSH 调用指南 |
| 代理避坑指南 | `/vol1/1000/projects/toyresearch/docs/AGENT_PROXY_TRAPS_AND_BEST_PRACTICES.md` | NO_PROXY、rclone、ChatgptREST |

### 训练项目

| 文档 | 路径 | 内容 |
|------|------|------|
| MiniMind 中文 README | `/vol1/1000/projects/toyresearch/minimind/README.md` | 64M 参数从 0 训练 |
| MiniMind 英文 README | `/vol1/1000/projects/toyresearch/minimind/README_en.md` | 英文版 |

### 外部 Maint 文档

| 文档 | 路径 | 内容 |
|------|------|------|
| GitNexus Embedding 基准 | `/vol1/maint/docs/2026-03-07_gitnexus_embeddings_yoga_benchmark.md` | snowflake-arctic-embed-xs 测试 |
| HomePC MCP 策略 | `/vol1/maint/docs/2026-03-07_gitnexus_homepc_priority_local_mcp.md` | HomePC 优先分析策略 |
| 模型路由架构 | `/vol1/maint/docs/2026-03-02_model_and_key_inventory.md` | LLMConnector + ModelRouter 全览 |

---

## 八、已知陷阱与注意事项

1. **CUDA_HOME 未设置**: HomePC 上 `CUDA_HOME` 环境变量为空，某些编译任务可能失败
2. **HomePC 双 GPU 分工**: GPU 0 常驻 ComfyUI (~16GB)，TRELLIS 必须指定 GPU 1
3. **Gemma4 实验产物残留**: `/REDACTED_HOME/models/quant-work/` 中有 58GB 已证伪的 BF16 + 14GB 已证伪的 TurboQuant GGUF，可清理以释放空间
4. **Ollama context 默认 262K**: qwen3.5 默认 262K 上下文会导致 KV cache 过大，建议限制到 32K
5. **Wan 2.1 14B 速度**: ~549s/clip，远慢于 LTX-13B (~30s)，生产使用需权衡
6. **ComfyUI LTX 模型混乱**: `diffusion_models/` 中的 LTX 文件是 symlink 到 `checkpoints/LTX-Video/`，不要重复下载
7. **Yoga → HomePC 路由**: `192.168.1.17` 是 DMZ 转发入口，HomePC 真实网卡 IP 是 `192.168.31.38`
8. **OpenClaw 未配置本地 provider**: 当前 OpenClaw 完全没有本地模型接入，需从零配置

---

*本交接文档基于 2026-05-06 实地探查数据。任何后续变更应在文档顶部追加修订记录。*
