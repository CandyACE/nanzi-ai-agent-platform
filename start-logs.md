# `dev.sh -d` 启动完整日志

以下日志来自 `yunshu-test` 环境执行 `./dev.sh -d` 的完整启动过程，包含 uv、Python 3.11、后端依赖、端口清理、前端构建和后端后台启动信息。

## 源码升级后的启动步骤

如果源码有升级更新，按以下顺序执行：

1. 拉取最新源码：

   ```bash
   git pull
   ```

2. 如果本次升级包含表结构变更，根据实际数据库类型执行对应目录下的数据库脚本：

   - MySQL：执行 `db-prod/` 下对应的迁移脚本。
   - PostgreSQL：执行 `db-prod-pg/` 下对应的迁移脚本。

   具体脚本和执行方式以对应目录中的 README 说明为准，不要混用两套数据库迁移脚本。

3. 启动服务：

   ```bash
   ./dev.sh -d
   ```

## 启动前配置

首次启动前，先复制环境变量模板，并根据实际部署环境修改配置：

```bash
cp env.example .env
vi .env
```

重点确认数据库、Redis、服务端口以及其他运行时配置已填写正确。

## 完整启动日志

```text
root@yunshu-test:/data/github/yunshu-ai-agent-platform# ./dev.sh -d
==================================================
       NanZi AI 开源智能体平台 · 本地开发启动工具         
       用法: ./dev.sh (前台调试) | ./dev.sh -d (后台常驻) 
==================================================
       启动环境信息
       ➜ uv: 未安装（启动时自动安装）
       ➜ Python 目标版本: 3.11
       ➜ 虚拟环境: .venv
       ➜ PyPI 镜像: https://pypi.tuna.tsinghua.edu.cn/simple
       ➜ DATABASE_TYPE: mysql (effective: mysql)
       ➜ 数据库地址: 10.90.10.73:3306/yunshu_ai_agent_platform
       ➜ Redis 地址: 10.90.10.73:6379/0
📦 未检测到 uv，正在通过官方安装脚本自动安装...
downloading uv 0.12.6 x86_64-unknown-linux-gnu
installing to /root/.local/bin
  uv
  uvx
everything's installed!

To add $HOME/.local/bin to your PATH, either restart your shell or run:

    source $HOME/.local/bin/env (sh, bash, zsh)
    source $HOME/.local/bin/env.fish (fish)
✅ uv 已准备完成：/root/.local/bin/uv

🧰 [1/4] 正在准备 uv、Python 3.11 和后端依赖...
✅ 已复用 Python 3.11 虚拟环境
📦 正在使用清华 PyPI 镜像安装后端依赖...
Checked 39 packages in 11.32s
✅ 后端依赖安装完成

🛑 [2/4] 正在检查并停止旧服务 (Port 8001)...
✅ 已停止旧进程 (PID: 414972
440192)

🚀 [3/4] 正在编译前端 (Building Frontend)...
npm notice run frontend@0.0.0 npx
npm notice run 'vite' build
vite v7.3.0 building client environment for production...
transforming (11) node_modules/axios/lib/axios.jsBrowserslist: browsers data (caniuse-lite) is 8 months old. Please run:
  npx update-browserslist-db@latest
  Why you should do it regularly: https://github.com/browserslist/update-db#readme
✓ 10455 modules transformed.
[plugin vite:reporter] 
(!) /data/github/yunshu-ai-agent-platform/frontend/src/utils/axios.ts is dynamically imported by /data/github/yunshu-ai-agent-platform/frontend/src/main.ts but also statically imported by /data/github/yunshu-ai-agent-platform/frontend/src/api/agent.ts, /data/github/yunshu-ai-agent-platform/frontend/src/api/artifact.ts, /data/github/yunshu-ai-agent-platform/frontend/src/api/changelog.ts, /data/github/yunshu-ai-agent-platform/frontend/src/api/metadata.ts, /data/github/yunshu-ai-agent-platform/frontend/src/api/model.ts, /data/github/yunshu-ai-agent-platform/frontend/src/api/portal.ts, /data/github/yunshu-ai-agent-platform/frontend/src/api/ragflow.ts, /data/github/yunshu-ai-agent-platform/frontend/src/api/task.ts, /data/github/yunshu-ai-agent-platform/frontend/src/api/tool.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/PortalNotificationBell.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/TraceLogViewer.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/chatbi/ChatBIMonitorDialog.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/chatbi/DatasetCapabilityMenu.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/chatbi/SavedReportBrowseModal.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/data-portal/DataPortalReportCreateModal.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/data-portal/DataPortalSceneSection.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/embed/AttachmentImageThumb.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/embed/ChatInput.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/embed/ChatSettings.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/embed/McpCascadeMenu.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/embed/MemoryBrowserDrawer.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/embed/SkillCascadeMenu.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/embed/WorkspaceBrowserDrawer.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/embed/WorkspaceDirectorySaveDialog.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/metadata/SmartImportWizard.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/personal/NotificationConfigs.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/personal/PersonalMemoryPanel.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/personal/PersonalTokenUsage.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/system/McpServerRegistry.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/system/McpToolTester.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/system/RedisKeyCleanupModal.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/task/TaskPromptComposer.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/composables/chat/useWorkspaceCanvas.ts, /data/github/yunshu-ai-agent-platform/frontend/src/composables/useBranding.ts, /data/github/yunshu-ai-agent-platform/frontend/src/composables/useContextUsage.ts, /data/github/yunshu-ai-agent-platform/frontend/src/composables/useDataPortalHome.ts, /data/github/yunshu-ai-agent-platform/frontend/src/composables/useDatasetPortal.ts, /data/github/yunshu-ai-agent-platform/frontend/src/composables/useKnowledgePortal.ts, /data/github/yunshu-ai-agent-platform/frontend/src/composables/useTokenQuota.ts, /data/github/yunshu-ai-agent-platform/frontend/src/composables/useWorkbenchHome.ts, /data/github/yunshu-ai-agent-platform/frontend/src/utils/cancelConversationRun.ts, /data/github/yunshu-ai-agent-platform/frontend/src/utils/conversationFinalize.ts, /data/github/yunshu-ai-agent-platform/frontend/src/utils/workspaceFilePreview.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/AgentDebug.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/AgentManagement.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/Dashboard.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/DataPortalHome.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/EmbedChat.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/ExampleManagement.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/KnowledgeBaseManagement.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/KnowledgeRetrievalTest.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/MemoryManagement.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/MetadataDatasets.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/NoPermission.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/Overview.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/PersonalCenter.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/PromptStudio.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/SkillsManagement.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/SystemConfig.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/TaskCenter.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/TokenStats.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/WidgetDebugger.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.

[plugin vite:reporter] 
(!) /data/github/yunshu-ai-agent-platform/frontend/src/composables/useBranding.ts is dynamically imported by /data/github/yunshu-ai-agent-platform/frontend/src/views/SystemConfig.vue?vue&type=script&setup=true&lang.ts but also statically imported by /data/github/yunshu-ai-agent-platform/frontend/src/App.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/embed/WelcomeDashboard.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/Dashboard.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/EmbedChat.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/Login.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/PersonalCenter.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/PersonalWorkbench.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/Users.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.

[plugin vite:reporter] 
(!) /data/github/yunshu-ai-agent-platform/frontend/src/utils/chartRenderer.ts is dynamically imported by /data/github/yunshu-ai-agent-platform/frontend/src/utils/agentscopeSseHandlers.ts but also statically imported by /data/github/yunshu-ai-agent-platform/frontend/src/components/MessageRenderer.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/components/embed/CanvasMarkdownRenderer.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/AgentDebug.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/EmbedChat.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.

[plugin vite:reporter] 
(!) /data/github/yunshu-ai-agent-platform/frontend/src/views/SkillsManagement.vue is dynamically imported by /data/github/yunshu-ai-agent-platform/frontend/src/components/embed/PersonalResourcesModal.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/router/index.ts but also statically imported by /data/github/yunshu-ai-agent-platform/frontend/src/views/PersonalCenter.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.

[plugin vite:reporter] 
(!) /data/github/yunshu-ai-agent-platform/frontend/src/utils/platformTimezone.ts is dynamically imported by /data/github/yunshu-ai-agent-platform/frontend/src/main.ts, /data/github/yunshu-ai-agent-platform/frontend/src/views/Login.vue?vue&type=script&setup=true&lang.ts but also statically imported by /data/github/yunshu-ai-agent-platform/frontend/src/views/TaskCenter.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.

[plugin vite:reporter] 
(!) /data/github/yunshu-ai-agent-platform/frontend/src/views/TaskCenter.vue is dynamically imported by /data/github/yunshu-ai-agent-platform/frontend/src/components/embed/PersonalResourcesModal.vue?vue&type=script&setup=true&lang.ts, /data/github/yunshu-ai-agent-platform/frontend/src/router/index.ts but also statically imported by /data/github/yunshu-ai-agent-platform/frontend/src/views/PersonalCenter.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.

dist/index.html                                           1.02 kB │ gzip:     0.54 kB
dist/assets/KaTeX_Size3-Regular-CTq5MqoE.woff             4.42 kB
dist/assets/KaTeX_Size4-Regular-Dl5lxZxV.woff2            4.93 kB
dist/assets/KaTeX_Size2-Regular-Dy4dx90m.woff2            5.21 kB
dist/assets/KaTeX_Size1-Regular-mCD8mA8B.woff2            5.47 kB
dist/assets/KaTeX_Size4-Regular-BF-4gkZK.woff             5.98 kB
dist/assets/KaTeX_Size2-Regular-oD1tc_U0.woff             6.19 kB
dist/assets/KaTeX_Size1-Regular-C195tn64.woff             6.50 kB
dist/assets/KaTeX_Caligraphic-Regular-Di6jR-x-.woff2      6.91 kB
dist/assets/KaTeX_Caligraphic-Bold-Dq_IR9rO.woff2         6.91 kB
dist/assets/KaTeX_Size3-Regular-DgpXs0kz.ttf              7.59 kB
dist/assets/KaTeX_Caligraphic-Regular-CTRA-rTL.woff       7.66 kB
dist/assets/KaTeX_Caligraphic-Bold-BEiXGLvX.woff          7.72 kB
dist/assets/KaTeX_Script-Regular-D3wIWfF6.woff2           9.64 kB
dist/assets/KaTeX_SansSerif-Regular-DDBCnlJ7.woff2       10.34 kB
dist/assets/KaTeX_Size4-Regular-DWFBv043.ttf             10.36 kB
dist/assets/KaTeX_Script-Regular-D5yQViql.woff           10.59 kB
dist/assets/KaTeX_Fraktur-Regular-CTYiF6lA.woff2         11.32 kB
dist/assets/KaTeX_Fraktur-Bold-CL6g_b3V.woff2            11.35 kB
dist/assets/KaTeX_Size2-Regular-B7gKUWhC.ttf             11.51 kB
dist/assets/KaTeX_SansSerif-Italic-C3H0VqGB.woff2        12.03 kB
dist/assets/KaTeX_SansSerif-Bold-D1sUS0GD.woff2          12.22 kB
dist/assets/KaTeX_Size1-Regular-Dbsnue_I.ttf             12.23 kB
dist/assets/KaTeX_SansSerif-Regular-CS6fqUqJ.woff        12.32 kB
dist/assets/KaTeX_Caligraphic-Regular-wX97UBjC.ttf       12.34 kB
dist/assets/KaTeX_Caligraphic-Bold-ATXxdsX0.ttf          12.37 kB
dist/assets/KaTeX_Fraktur-Regular-Dxdc4cR9.woff          13.21 kB
dist/assets/KaTeX_Fraktur-Bold-BsDP51OF.woff             13.30 kB
dist/assets/KaTeX_Typewriter-Regular-CO6r4hn1.woff2      13.57 kB
dist/assets/KaTeX_SansSerif-Italic-DN2j7dab.woff         14.11 kB
dist/assets/KaTeX_SansSerif-Bold-DbIhKOiC.woff           14.41 kB
dist/assets/KaTeX_Typewriter-Regular-C0xS9mPB.woff       16.03 kB
dist/assets/KaTeX_Math-BoldItalic-CZnvNsCZ.woff2         16.40 kB
dist/assets/KaTeX_Math-Italic-t53AETM-.woff2             16.44 kB
dist/assets/KaTeX_Script-Regular-C5JkGWo-.ttf            16.65 kB
dist/assets/KaTeX_Main-BoldItalic-DxDJ3AOS.woff2         16.78 kB
dist/assets/KaTeX_Main-Italic-NWA7e6Wa.woff2             16.99 kB
dist/assets/KaTeX_Math-BoldItalic-iY-2wyZ7.woff          18.67 kB
dist/assets/KaTeX_Math-Italic-DA0__PXp.woff              18.75 kB
dist/assets/KaTeX_Main-BoldItalic-SpSLRI95.woff          19.41 kB
dist/assets/KaTeX_SansSerif-Regular-BNo7hRIc.ttf         19.44 kB
dist/assets/KaTeX_Fraktur-Regular-CB_wures.ttf           19.57 kB
dist/assets/KaTeX_Fraktur-Bold-BdnERNNW.ttf              19.58 kB
dist/assets/KaTeX_Main-Italic-BMLOBm91.woff              19.68 kB
dist/assets/KaTeX_SansSerif-Italic-YYjJ1zSn.ttf          22.36 kB
dist/assets/KaTeX_SansSerif-Bold-CFMepnvq.ttf            24.50 kB
dist/assets/KaTeX_Main-Bold-Cx986IdX.woff2               25.32 kB
dist/assets/KaTeX_Main-Regular-B22Nviop.woff2            26.27 kB
dist/assets/KaTeX_Typewriter-Regular-D3Ib7_Hf.ttf        27.56 kB
dist/assets/KaTeX_AMS-Regular-BQhdFMY1.woff2             28.08 kB
dist/assets/KaTeX_Main-Bold-Jm3AIy58.woff                29.91 kB
dist/assets/KaTeX_Main-Regular-Dr94JaBh.woff             30.77 kB
dist/assets/KaTeX_Math-BoldItalic-B3XSjfu4.ttf           31.20 kB
dist/assets/KaTeX_Math-Italic-flOr_0UB.ttf               31.31 kB
dist/assets/KaTeX_Main-BoldItalic-DzxPMmG6.ttf           32.97 kB
dist/assets/KaTeX_AMS-Regular-DMm9YOAa.woff              33.52 kB
dist/assets/KaTeX_Main-Italic-3WenGoN9.ttf               33.58 kB
dist/assets/KaTeX_Main-Bold-waoOVXN0.ttf                 51.34 kB
dist/assets/KaTeX_Main-Regular-ypZvNtVU.ttf              53.58 kB
dist/assets/KaTeX_AMS-Regular-DRggAlZN.ttf               63.63 kB
dist/assets/EmbedLayout-KnsO1mLS.css                      0.07 kB │ gzip:     0.09 kB
dist/assets/KnowledgeMetrics-D6YAjViR.css                 0.07 kB │ gzip:     0.08 kB
dist/assets/ExampleManagement-B1NmZElV.css                0.12 kB │ gzip:     0.11 kB
dist/assets/Chat-DGF8WCW8.css                             0.14 kB │ gzip:     0.12 kB
dist/assets/DataSourceManagement-CRAIa7O3.css             0.17 kB │ gzip:     0.13 kB
dist/assets/KnowledgeBaseManagement-BgGHe52o.css          0.27 kB │ gzip:     0.16 kB
dist/assets/KnowledgeRetrievalTest-BTv9WpvT.css           1.14 kB │ gzip:     0.36 kB
dist/assets/EmbedChat-CgyS0Ty0.css                       22.11 kB │ gzip:     4.09 kB
dist/assets/index-K3psCyJS.css                          640.75 kB │ gzip:    98.31 kB
dist/assets/McpManagement-B640hGGb.js                     0.06 kB │ gzip:     0.08 kB
dist/assets/PersonalMemoryPanel-CUFM0ypW.js               0.06 kB │ gzip:     0.08 kB
dist/assets/PersonalTokenUsage-C5UkwvVf.js                0.06 kB │ gzip:     0.08 kB
dist/assets/DataPortalHome-CeolCSG1.js                    0.06 kB │ gzip:     0.08 kB
dist/assets/clone-BC5cznD3.js                             0.09 kB │ gzip:     0.11 kB
dist/assets/channel-BXSOGbYG.js                           0.11 kB │ gzip:     0.12 kB
dist/assets/init-Gi6I4Gst.js                              0.15 kB │ gzip:     0.13 kB
dist/assets/chunk-QZHKN3VN-CLqhM6nh.js                    0.19 kB │ gzip:     0.16 kB
dist/assets/chunk-4BX2VUAB-CEqTAPCg.js                    0.22 kB │ gzip:     0.17 kB
dist/assets/chunk-55IACEB6-dj8l6Fza.js                    0.22 kB │ gzip:     0.21 kB
dist/assets/CollectionSync.vue-DsbzKTpz.js                0.27 kB │ gzip:     0.23 kB
dist/assets/CollectionCookies.vue-DbyVQ1Pp.js             0.28 kB │ gzip:     0.23 kB
dist/assets/CollectionScripts.vue-CjLoxIsx.js             0.28 kB │ gzip:     0.23 kB
dist/assets/ViewLayoutContent.vue-CVEk_XRA.js             0.31 kB │ gzip:     0.23 kB
dist/assets/EmbedLayout-DI5CEQ6k.js                       0.33 kB │ gzip:     0.27 kB
dist/assets/use-tree-walker-77z6FSy4.js                   0.33 kB │ gzip:     0.27 kB
dist/assets/ViewLayout.vue-BCaBRTzI.js                    0.34 kB │ gzip:     0.26 kB
dist/assets/stateDiagram-v2-4FDKWEC3-DB5F7hEf.js          0.36 kB │ gzip:     0.27 kB
dist/assets/chunk-FMBD7UC4-BmU1Bonr.js                    0.36 kB │ gzip:     0.27 kB
dist/assets/ArrowLeftIcon-BcE2gle5.js                     0.36 kB │ gzip:     0.28 kB
dist/assets/classDiagram-2ON5EDUG-BwFDLwfP.js             0.40 kB │ gzip:     0.28 kB
dist/assets/classDiagram-v2-WZHVMYZB-BwFDLwfP.js          0.40 kB │ gzip:     0.28 kB
dist/assets/chunk-QN33PNHL-CaUPGvdN.js                    0.50 kB │ gzip:     0.36 kB
dist/assets/EditSidebarListElement.vue-C_VMsdGG.js        0.53 kB │ gzip:     0.36 kB
dist/assets/ViewLayoutSection.vue-DOJ7fU1J.js             0.55 kB │ gzip:     0.39 kB
dist/assets/min-CTY7pnm9.js                               0.59 kB │ gzip:     0.36 kB
dist/assets/infoDiagram-WHAUD3N6-BRxJq6o6.js              0.62 kB │ gzip:     0.42 kB
dist/assets/ScalarAsciiArt.vue-ClR5kctp.js                0.96 kB │ gzip:     0.61 kB
dist/assets/ScalarHotkey.vue-B-1NR6F0.js                  1.13 kB │ gzip:     0.71 kB
dist/assets/ordinal-Cboi1Yqb.js                           1.19 kB │ gzip:     0.57 kB
dist/assets/chunk-TZMSLE5B-WmSDF4Js.js                    1.43 kB │ gzip:     0.63 kB
dist/assets/Form.vue-DrW5qkDg.js                          1.52 kB │ gzip:     0.84 kB
dist/assets/CollectionAuthentication.vue-C5crlOiU.js      1.57 kB │ gzip:     0.84 kB
dist/assets/DeleteSidebarListElement.vue-DR2FORep.js      1.59 kB │ gzip:     0.87 kB
dist/assets/EmptyState.vue-BZk8ZAhB.js                    1.87 kB │ gzip:     0.65 kB
dist/assets/Draggable.vue-wUkpC3jn.js                     1.93 kB │ gzip:     1.03 kB
dist/assets/CommandActionInput.vue-CZ4Tvof5.js            1.94 kB │ gzip:     1.05 kB
dist/assets/useWorkbenchHome-CEdZv7Mh.js                  2.35 kB │ gzip:     1.27 kB
dist/assets/SidebarButton.vue-BYb-oWJG.js                 2.64 kB │ gzip:     1.38 kB
dist/assets/CollectionOverview.vue-DPruGYea.js            3.00 kB │ gzip:     1.34 kB
dist/assets/CollectionSettings.vue-2FShDyIP.js            3.07 kB │ gzip:     1.50 kB
dist/assets/arc--iCk9KfO.js                               3.43 kB │ gzip:     1.47 kB
dist/assets/Chat-DQQwZhM8.js                              3.76 kB │ gzip:     1.84 kB
dist/assets/DataTableHeader.vue-oQ5Tzm_z.js               3.82 kB │ gzip:     1.45 kB
dist/assets/CollectionServers.vue-DpkGf2Hh.js             3.90 kB │ gzip:     1.83 kB
dist/assets/SidebarListElement.vue-DFecApIu.js            4.08 kB │ gzip:     1.71 kB
dist/assets/diagram-S2PKOQOG-Blx9SUSK.js                  4.24 kB │ gzip:     1.85 kB
dist/assets/defaultLocale-DX6XiGOO.js                     4.69 kB │ gzip:     2.18 kB
dist/assets/Cookies.vue-6rCasC_s.js                       4.85 kB │ gzip:     2.08 kB
dist/assets/Collection.vue-DgyxPtbr.js                    4.94 kB │ gzip:     2.15 kB
dist/assets/pieDiagram-ADFJNKIX-CQ4p7pjs.js               5.18 kB │ gzip:     2.29 kB
dist/assets/linear-DbO18k2X.js                            5.65 kB │ gzip:     2.31 kB
dist/assets/diagram-QEK2KX5R-D_Eb3981.js                  5.85 kB │ gzip:     2.47 kB
dist/assets/EnvironmentModal.vue-DUZrPe3g.js              6.17 kB │ gzip:     2.34 kB
dist/assets/ScenarioTemplateDetail-CDrQTWl4.js            6.51 kB │ gzip:     2.56 kB
dist/assets/IconSelector.vue-Bf7ZFh_K.js                  7.64 kB │ gzip:     3.15 kB
dist/assets/_baseUniq-xTyzy0eb.js                         8.48 kB │ gzip:     3.53 kB
dist/assets/Environment.vue-Bm6eXDEm.js                   8.74 kB │ gzip:     3.39 kB
dist/assets/Settings.vue-B6s9GKCt.js                      8.75 kB │ gzip:     2.72 kB
dist/assets/graph-DPOflf9I.js                             9.36 kB │ gzip:     3.20 kB
dist/assets/CollectionEnvironment.vue-DE_75Ky8.js         9.45 kB │ gzip:     3.43 kB
dist/assets/stateDiagram-FKZM4ZOC-B7R2O1jV.js            10.35 kB │ gzip:     3.62 kB
dist/assets/ScenarioTemplates-BoPh2WnP.js                10.72 kB │ gzip:     3.67 kB
dist/assets/dagre-6UL2VRFP-dRV3_wRM.js                   10.96 kB │ gzip:     4.09 kB
dist/assets/KnowledgeMetrics-Deq7jowh.js                 12.07 kB │ gzip:     4.34 kB
dist/assets/mediaTypes-xarEZ3E8.js                       15.46 kB │ gzip:     3.73 kB
dist/assets/diagram-PSM6KHXK-DJBsgVbz.js                 15.80 kB │ gzip:     5.65 kB
dist/assets/TokenStats-DsDEVYy-.js                       15.92 kB │ gzip:     5.08 kB
dist/assets/ScenarioTemplateInstall-BA-0WzEt.js          16.95 kB │ gzip:     5.40 kB
dist/assets/kanban-definition-3W4ZIXB7-DVDvAPGE.js       20.17 kB │ gzip:     7.15 kB
dist/assets/mindmap-definition-VGOIOE7T-CEQkBK8p.js      20.88 kB │ gzip:     7.27 kB
dist/assets/sankeyDiagram-TZEHDZUN-DAVwOFBE.js           22.08 kB │ gzip:     8.12 kB
dist/assets/RequestAuth.vue-CnK9anPM.js                  22.26 kB │ gzip:     6.86 kB
dist/assets/journeyDiagram-XKPGCS4Q-Uton55Gq.js          23.51 kB │ gzip:     8.31 kB
dist/assets/timeline-definition-IT6M3QCI-yLa7BoBS.js     23.56 kB │ gzip:     8.21 kB
dist/assets/KnowledgeRetrievalTest-BQ7SkrGq.js           24.00 kB │ gzip:     6.87 kB
dist/assets/gitGraphDiagram-NY62KEGX-DpbDQpVY.js         24.07 kB │ gzip:     7.41 kB
dist/assets/erDiagram-Q2GNP2WA-DY7IYaJS.js               25.21 kB │ gzip:     8.82 kB
dist/assets/layout-CzAv9XVp.js                           29.28 kB │ gzip:    10.52 kB
dist/assets/requirementDiagram-UZGBJVZJ-Db5Llspv.js      30.05 kB │ gzip:     9.41 kB
dist/assets/PersonalWorkbench-CJOXcGFB.js                30.29 kB │ gzip:     8.18 kB
dist/assets/quadrantDiagram-AYHSOK5B-DAgthtR8.js         33.81 kB │ gzip:     9.94 kB
dist/assets/chunk-DI55MBZ5-LBqTpLR-.js                   36.33 kB │ gzip:    11.85 kB
dist/assets/WidgetDebugger-aanfAMcE.js                   37.90 kB │ gzip:    13.41 kB
dist/assets/xychartDiagram-PRI3JC2R--yKRyuEX.js          40.18 kB │ gzip:    11.43 kB
dist/assets/RequestRoot.vue-dYsyEOP6.js                  44.93 kB │ gzip:    15.36 kB
dist/assets/chunk-B4BG7PRW-O-1z-fTL.js                   45.31 kB │ gzip:    14.71 kB
dist/assets/Roles-CJcDEVFp.js                            50.14 kB │ gzip:    13.25 kB
dist/assets/MemoryManagement-DY-39KC3.js                 57.12 kB │ gzip:    16.30 kB
dist/assets/ExampleManagement-BvCYdjO1.js                57.14 kB │ gzip:    18.34 kB
dist/assets/flowDiagram-NV44I4VS-IcGWPrds.js             60.42 kB │ gzip:    19.43 kB
dist/assets/DataSourceManagement-D4e7mrdi.js             63.03 kB │ gzip:    18.87 kB
dist/assets/ganttDiagram-JELNMOA3-DbUtYzzX.js            68.27 kB │ gzip:    23.13 kB
dist/assets/c4Diagram-YG6GDRKO-DWAOoW8x.js               70.10 kB │ gzip:    19.67 kB
dist/assets/blockDiagram-VD42YOAC-FIkcw7l3.js            71.75 kB │ gzip:    20.49 kB
dist/assets/cose-bilkent-S5V4N54A-BvMowTBy.js            81.66 kB │ gzip:    22.45 kB
dist/assets/sequenceDiagram-WL72ISMW-kS6Pdn8L.js         97.78 kB │ gzip:    26.85 kB
dist/assets/Request.vue-Bve31L53.js                     102.83 kB │ gzip:    29.53 kB
dist/assets/KnowledgeBaseManagement-B7aLoShw.js         110.50 kB │ gzip:    30.30 kB
dist/assets/architectureDiagram-VXUJARFQ-l9Ym3IV3.js    148.46 kB │ gzip:    41.97 kB
dist/assets/katex-Buwston5.js                           260.49 kB │ gzip:    77.35 kB
dist/assets/EmbedChat-DqqaSN1F.js                       354.89 kB │ gzip:    97.87 kB
dist/assets/treemap-KMMF4GRG-CPZp_zPE.js                373.08 kB │ gzip:    92.29 kB
dist/assets/cytoscape.esm-DwGIvGbm.js                   441.07 kB │ gzip:   141.26 kB
dist/assets/index-BVn2Vh6h.js                         9,075.04 kB │ gzip: 2,652.70 kB

(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
✓ built in 8m 46s
✅ 前端编译成功！

🔥 [4/4] 正在后台启动后端服务 (Starting Backend in Daemon Mode)...
✅ 后端服务已在后台启动！
   ➜ 服务 PID: 440533
   ➜ 访问端口: http://0.0.0.0:8001
   ➜ 日志文件: server.log
   ➜ 查看实时日志命令: tail -f server.log
root@yunshu-test:/data/github/yunshu-ai-agent-platform# 
```
