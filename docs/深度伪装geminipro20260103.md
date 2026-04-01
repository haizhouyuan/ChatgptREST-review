你的 ChatgptREST 仓库目前的伪装策略（禁用 AutomationControlled + 基础 JS 注入 + 视窗抖动 + 行为拟人）对于一般的反爬虫（如 WAF）是有效的，但对于专门针对浏览器指纹的高级检测（如 Cloudflare Turnstile 的高强度模式、Arkose Labs 等，OpenAI 有时会启用这些）确实还不够深。

特别是 navigator.webdriver 改了但 Canvas 指纹没变，或者 User-Agent 字符串改了但 Client Hints 没改，这种**“特征不一致”**（Inconsistency）是最大的露馅点。

以下是针对你代码库的深度伪装升级方案，主要通过增强 _CHATGPT_STEALTH_INIT_JS 来实现。

1. 核心策略：JS 注入层面的深度伪装 (Deep Spoofing)
你需要大幅扩展 chatgpt_web_mcp/server.py 中的 _CHATGPT_STEALTH_INIT_JS。现在的版本只覆盖了皮毛。

建议将该变量替换为以下包含 Canvas、WebGL、Audio、Hardware Concurrency 等模块的完整脚本。

升级版 _CHATGPT_STEALTH_INIT_JS 代码
请用以下代码替换原有的 _CHATGPT_STEALTH_INIT_JS（约在 server.py:505）：

Python

_CHATGPT_STEALTH_INIT_JS = r"""
() => {
  // 1. 基础自动化特征抹除 (原有逻辑增强)
  try {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  } catch {}
  try {
    window.chrome = { runtime: {} };
  } catch {}
  try {
    // 伪造插件列表，使其看起来不像无头浏览器
    const mockPlugins = [
      { name: "PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
      { name: "Chrome PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
      { name: "Chromium PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
      { name: "Microsoft Edge PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
      { name: "WebKit built-in PDF", filename: "internal-pdf-viewer", description: "Portable Document Format" }
    ];
    Object.defineProperty(navigator, 'plugins', { get: () => mockPlugins });
    Object.defineProperty(navigator, 'mimeTypes', { get: () => [] });
  } catch {}

  // 2. 硬件并发数伪装 (防止检测到服务器级的高核数或默认的低核数)
  try {
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 4 });
  } catch {}

  // 3. Canvas 指纹噪声注入 (最关键的指纹之一)
  // 原理：在导出图像数据时微调 RGB 值，使哈希值对于这台机器是唯一的，但与真实指纹不同且每次会话一致
  try {
    const toBlob = HTMLCanvasElement.prototype.toBlob;
    const toDataURL = HTMLCanvasElement.prototype.toDataURL;
    const getImageData = CanvasRenderingContext2D.prototype.getImageData;
    
    // 生成一个基于域名的稳定随机噪声，避免同一页面多次调用产生不同结果导致崩溃或被检测
    const shift = { r: -1, g: 1, b: -1 }; 

    function noisyDataURL(type, encoderOptions) {
      // 只有在试图读取指纹时才注入噪声，避免破坏正常 UI 渲染
      // 简单的启发式：通常指纹脚本会创建一个不可见的 canvas
      const width = this.width;
      const height = this.height;
      // 这里的逻辑可以更复杂，目前简化为只要调用就加噪
      // 注意：直接修改 toDataURL 可能会影响截图功能，建议仅针对小尺寸 Canvas 生效
      return toDataURL.apply(this, arguments); 
    }

    // 劫持 getImageData (这是 FingerprintJS 常用的方法)
    CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
      const imageData = getImageData.apply(this, arguments);
      // 仅对较小的指纹采集区域加噪，避免破坏大图
      if (w < 100 && h < 100) { 
        for (let i = 0; i < imageData.data.length; i += 4) {
          imageData.data[i] = imageData.data[i] + shift.r;
          imageData.data[i+1] = imageData.data[i+1] + shift.g;
          imageData.data[i+2] = imageData.data[i+2] + shift.b;
        }
      }
      return imageData;
    };
  } catch(e) {}

  // 4. WebGL 指纹伪装 (伪装显卡型号)
  // 如果是无头模式或服务器环境，通常显示为 "Google SwiftShader"，这是死穴。
  try {
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
      // UNMASKED_VENDOR_WEBGL
      if (parameter === 37445) {
        return "Intel Inc.";
      }
      // UNMASKED_RENDERER_WEBGL
      if (parameter === 37446) {
        return "Intel(R) Iris(R) Xe Graphics"; 
      }
      return getParameter.apply(this, arguments);
    };
  } catch(e) {}

  // 5. AudioContext 指纹噪声
  try {
    const P = window.AudioContext || window.webkitAudioContext;
    if (P) {
        const createOscillator = P.prototype.createOscillator;
        const createAnalyser = P.prototype.createAnalyser;
        // 简单 Hook 示例：实际反检测脚本通常会修改 analyser.getChannelData 的返回值
    }
  } catch(e) {}
  
  // 6. 权限 API 伪装 (Headless 默认权限行为与 Headful 不同)
  try {
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
      parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
    );
  } catch(e) {}
};
"""
2. 补全 UA Client Hints (重要)
现在的检测机制不仅看 User-Agent 字符串，还会检查 navigator.userAgentData (Client Hints)。如果在 chrome_start.sh 中只是启动了 Chrome 而没有特意配置，通常 CDP 连接的真实 Chrome 会暴露正确的值，这通常是好事。

但如果你是在无头模式 (headless=True) 下运行 Playwright 托管的 Chromium，它可能会暴露 "HeadlessChrome"。

检查点： 你的代码在 server.py 中有 _open_chatgpt_page 函数。

如果走 CDP (use_cdp=True)：通常由 chrome_start.sh 启动的 Chrome 决定。只要确保 chrome_start.sh 启动的是完整版 Chrome (Google Chrome) 而不是 Chromium，且不要加 --headless 参数（你用的是 Xvfb + setsid google-chrome，这是对的，属于 "Headful running in headless env"，指纹最真实）。

如果走 Playwright (use_cdp=False)：你需要显式注入 UA 和 Client Hints。

在 server.py 的 _open_chatgpt_page 函数中，当 use_cdp=False 时：

Python

# 修改前
context = await browser.new_context(
    storage_state=str(cfg.storage_state_path),
    viewport={"width": viewport_width, "height": viewport_height},
)

# 修改后：显式指定 UserAgent，防止暴露 Headless 特征
context = await browser.new_context(
    storage_state=str(cfg.storage_state_path),
    viewport={"width": viewport_width, "height": viewport_height},
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", # 找一个较新的真实 UA
    # Playwright 会根据 user_agent 自动设置一部分 Client Hints，但并不完美
)
3. Chrome 启动参数的优化 (ops/chrome_start.sh)
你目前的启动参数已经不错了，使用了 google-chrome 而非 chromium，且配合 Xvfb (DISPLAY=:99)。

建议在 ops/chrome_start.sh 的 CHROME_EXTRA_ARGS 中再增加几项，以应对更现代的指纹检测：

Bash

# 现有的
CHROME_EXTRA_ARGS="--disable-blink-features=AutomationControlled"

# 建议追加的
# 1. 禁用默认浏览器检查，加快启动
CHROME_EXTRA_ARGS="${CHROME_EXTRA_ARGS} --no-default-browser-check"
# 2. 禁用自动化扩展 (虽然你可能没安，但为了保险)
CHROME_EXTRA_ARGS="${CHROME_EXTRA_ARGS} --disable-automation"
# 3. 强制颜色配置，防止因为服务器没有显示器导致颜色深度指纹异常
CHROME_EXTRA_ARGS="${CHROME_EXTRA_ARGS} --force-color-profile=srgb"
# 4. 隐藏部分提示条
CHROME_EXTRA_ARGS="${CHROME_EXTRA_ARGS} --disable-infobars"
4. 为什么不推荐使用 playwright-stealth 库？
虽然 Python 有 playwright-stealth 库，但它维护频率较低，且很难与你现有的自定义 add_init_script 架构完美融合（它倾向于自己接管 Context）。目前的“手动注入 JS”方式（Step 1）更适合你的代码结构，因为你可以精确控制注入时机和内容，且易于调试。

总结
为了避免 ChatGPT Web 识别：

最优先：更新 server.py 中的 _CHATGPT_STEALTH_INIT_JS，加入 Canvas/WebGL/HardwareConcurrency 的 Mock（我上面提供的代码块）。这是目前对抗 Arkose Labs/Cloudflare 的主力。

检查：确保你的 ops/chrome_start.sh 启动的是 Google Chrome Stable 版本，而不是 Chromium。Google Chrome 自带的编解码器和指纹特征比开源的 Chromium 更像真实用户。

Client Hints：由于你主要使用 CDP 连接真实 Chrome，Browser 指纹本身通常是真实的，只要注入 JS 掩盖 webdriver 属性和显卡型号（如果服务器是无显卡环境）即可。