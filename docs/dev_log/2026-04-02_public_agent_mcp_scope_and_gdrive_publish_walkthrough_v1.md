# 2026-04-02 Public Agent MCP Scope And GDrive Publish Walkthrough v1

## 这轮做了什么

这轮完成了两件事：

1. 重新核查 `publicagentmcp` 的当前 scope，判断它是否已经超出“封装 `chatgpt_web.ask` / `gemini_web.ask`”的原始目标
2. 把用户指定的两份 matrix 文档发布到 Google Drive

## 代码核查结论

核查结果是：

1. `consult` 现在更像早期历史层的专项复核分支，不属于 ask facade 的最小闭环
2. `publicagentmcp` 当前公开的 6 个工具里，`repo_bootstrap` 和 `repo_doc_obligations` 已明显超出“ask 封装”目标
3. `/v3/agent/turn` 现在还挂了 `workspace`、`image`、`consult`、direct Gemini、controller/chatgpt 等多类分支

本轮对应 review：

- [2026-04-02_public_agent_mcp_scope_and_pruning_review_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_public_agent_mcp_scope_and_pruning_review_v1.md)

## Google Drive 发布结果

本轮发布的文件：

1. [planning_task_surface_and_lane_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_planning_task_surface_and_lane_matrix_v1.md)
2. [planning_task_surface_and_lane_matrix_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-01_planning_task_surface_and_lane_matrix_walkthrough_v1.md)

发布目标目录：

- `gdrive:published/chatgptrest_docs/2026-04-02/`

远端对象：

1. `gdrive:published/chatgptrest_docs/2026-04-02/2026-04-01_planning_task_surface_and_lane_matrix_v1.md`
2. `gdrive:published/chatgptrest_docs/2026-04-02/2026-04-01_planning_task_surface_and_lane_matrix_walkthrough_v1.md`

Drive 打开链接：

1. `https://drive.google.com/open?id=1s47be4T97keHGnN2tKlKDInhCLCZBq_v`
2. `https://drive.google.com/open?id=1fwenBBzJMqw2qHx5nIRc5HMgddaCDeZe`

## 一个过程细节

第一次通过 skill wrapper `push` 时，主文档那份只回显了目标 remote path，但远端目录里并未实际可见。

后续改为直接：

- `rclone copyto /local/file gdrive:published/...`

再次验证后，两个文件都已在远端目录中可见，并且成功拿到了 Drive link。
