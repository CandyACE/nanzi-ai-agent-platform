# 源码与 Docker 部署启动完整日志

以下日志来自 `yunshu-test` 环境执行 `./dev.sh -d` 的完整启动过程，包含 uv、Python 3.11、后端依赖、端口清理、前端构建和后端后台启动信息。

## Docker 打包启动步骤

以下日志来自 `laplace-app` 环境执行源码更新和 Docker 镜像构建的过程，包含 `git pull`、`docker/build_linux_x86.sh` 以及镜像构建输出。

```text
root@laplace-app:~/workspace/github/yunshu-ai-agent-platform# git pull
Updating 0d367ca6..6269bf9f
Fast-forward
 DEVELOPMENT.md                                                                |   49 +-
 FAQ.md                                                                        |  464 +++++++++++++++-
 HOW_TO_INSTALL.md                                                             |  124 +++--
 README.md                                                                     |   20 +-
 README_EN.md                                                                  |   20 +-
 app/api/portal/endpoints/metadata.py                                          |   53 +-
 app/api/portal/endpoints/models.py                                            |    8 +-
 app/api/portal/endpoints/saved_reports.py                                     |  476 ++++++++++++++--
 app/api/v1/endpoints/browser.py                                               |  105 +++-
 app/api/v1/endpoints/chat.py                                                  |   15 +-
 app/schemas/ai_model.py                                                       |   46 +-
 app/schemas/browser.py                                                        |    1 +
 app/schemas/metadata.py                                                       |    8 +
 app/services/ai/agent_prompts.py                                              |    5 +-
 app/services/ai/agent_readiness.py                                            |   20 +-
 app/services/ai/agent_service.py                                              |  259 +++++++--
 app/services/ai/browser/__init__.py                                           |    2 +
 app/services/ai/browser/browser_policy.py                                     |   33 ++
 app/services/ai/browser/browser_profile_service.py                            |   38 +-
 app/services/ai/browser/browser_runtime.py                                    |   72 ++-
 app/services/ai/browser/browser_session_service.py                            |   92 +--
 app/services/ai/browser/browser_worker.py                                     |  415 +++++++++++---
 app/services/ai/config.py                                                     |    6 +-
 app/services/ai/context_manager.py                                            |   48 +-
 app/services/ai/dispatcher.py                                                 |    1 +
 app/services/ai/knowledge_utils.py                                            |   10 +-
 app/services/ai/memory_service.py                                             |   50 +-
 app/services/ai/multimodal_support.py                                         |   47 +-
 app/services/ai/prompt_assembler.py                                           |    8 +-
 app/services/ai/reasoning.py                                                  |   21 +-
 app/services/ai/route_progress.py                                             |   53 ++
 app/services/ai/router_service.py                                             |  264 ++++++++-
 app/services/ai/runners/assistant_agent_runner.py                             |   23 +-
 app/services/ai/runners/chatbi/react_stream.py                                |   34 ++
 app/services/ai/runners/knowledge_agent_runner.py                             |    7 +
 app/services/ai/runtime/agentscope/chat.py                                    |   27 +-
 app/services/ai/runtime/agentscope/context_breakdown.py                       |   35 +-
 app/services/ai/runtime/agentscope/middleware.py                              |   28 +-
 app/services/ai/runtime/agentscope/models.py                                  |   86 ++-
 app/services/ai/runtime/agentscope/process_narration.py                       |   31 ++
 app/services/ai/runtime/agentscope/process_timeline_snapshot.py               |   17 +-
 app/services/ai/runtime/agentscope/tools.py                                   |  107 +++-
 app/services/ai/runtime/execution_observability.py                            |   91 +++
 app/services/ai/runtime/stream_repetition_detector.py                         |  124 +++++
 app/services/ai/runtime/tool_loop_detector.py                                 |    4 +-
 app/services/ai/skill_resolver.py                                             |   80 ++-
 app/services/ai/tools/agent_delegate_tool.py                                  |   28 +-
 app/services/ai/tools/browser_tools.py                                        |   57 +-
 app/services/ai/tools/tool_compat.py                                          |   12 +-
 app/services/metadata_generator.py                                            |  238 ++++++--
 app/services/metadata_service.py                                              |   37 +-
 data/docs/FAQ.md                                                              |  464 +++++++++++++++-
 data/docs/README.md                                                           |   24 +-
 db-prod-pg/V31-add_agent_legacy_primary_capabilities.sql                      |   16 +
 db-prod/README.md                                                             |   28 +-
 db-prod/V131-add_agent_legacy_primary_capabilities.sql                        |   16 +
 db-prod/apply-sql-native.sh                                                   |   93 +++-
 db-prod/apply-sql.sh                                                          |   39 +-
 db-prod/apply_sql.py                                                          |   56 +-
 dev.sh                                                                        |  254 ++++++++-
 docker/Dockerfile                                                             |    2 +-
 docs/images/weixin-group.png                                                  |  Bin 418769 -> 475391 bytes
 docs/superpowers/plans/2026-08-25-codemirror-sql-editor.md                    |  105 ++++
 docs/superpowers/plans/2026-08-25-route-progress-sse-display.md               |  434 +++++++++++++++
 docs/superpowers/plans/2026-08-25-saved-report-dynamic-parameter-shortcuts.md |   51 ++
 docs/superpowers/plans/2026-08-25-unify-saved-report-editor.md                |  218 ++++++++
 docs/superpowers/plans/2026-08-26-agent-execution-latency-optimization.md     |  287 ++++++++++
 docs/superpowers/plans/2026-08-26-dev-sh-python-bootstrap.md                  |  244 ++++++++
 docs/superpowers/plans/2026-08-26-docker-terminal-welcome-banner.md           |  229 ++++++++
 docs/superpowers/plans/2026-08-26-k8s-deploy.md                               |   27 +
 docs/superpowers/plans/2026-08-26-saved-report-ui-ux.md                       |  160 ++++++
 docs/superpowers/plans/2026-08-26-saved-report-view-switch.md                 |  152 +++++
 docs/superpowers/plans/2026-08-26-smart-metric-detail.md                      |  157 ++++++
 docs/superpowers/plans/2026-08-26-thinking-tool-choice-fallback.md            |  120 ++++
 docs/superpowers/specs/2026-08-25-auto-routing-latency-unification-design.md  |  341 ++++++++++++
 docs/superpowers/specs/2026-08-25-codemirror-sql-editor-design.md             |   35 ++
 docs/superpowers/specs/2026-08-25-unify-saved-report-editor-design.md         |   64 +++
 docs/superpowers/specs/2026-08-26-dev-sh-python-bootstrap-design.md           |   90 +++
 docs/superpowers/specs/2026-08-26-docker-terminal-welcome-banner-design.md    |  153 +++++
 docs/superpowers/specs/2026-08-26-k8s-deploy-design.md                        |   90 +++
 docs/superpowers/specs/2026-08-26-saved-report-view-switch-design.md          |   46 ++
 docs/superpowers/specs/2026-08-26-smart-metric-detail-design.md               |   44 ++
 docs/superpowers/specs/2026-08-26-thinking-tool-choice-fallback-design.md     |   53 ++
 frontend/package-lock.json                                                    |   78 +++
 frontend/package.json                                                         |    4 +
 frontend/src/api/metadata.ts                                                  |   12 +-
 frontend/src/components/ConfirmModal.vue                                      |    8 +-
 frontend/src/components/PortalNotificationBell.vue                            |   10 +-
 frontend/src/components/agent/AgentFlowGuideBanner.vue                        |  278 ++++++++++
 frontend/src/components/chat/ChatExecutionTimeline.vue                        |   63 ++-
 frontend/src/components/chat/ChatThinkingHeader.vue                           |   30 +-
 frontend/src/components/chat/DockerTerminalModal.vue                          |  158 ++++--
 frontend/src/components/chat/SavedReportEditorModal.vue                       |  143 -----
 frontend/src/components/chat/SavedReportRunModal.vue                          |  121 +++-
 frontend/src/components/chatbi/DatasetCapabilityMenu.vue                      |  455 ++++++++++-----
 frontend/src/components/chatbi/DatasetPortalDrawer.vue                        |    1 +
 frontend/src/components/chatbi/SavedReportBrowseModal.vue                     |   12 +-
 frontend/src/components/chatbi/SavedReportItemCard.vue                        |  225 +++++++-
 frontend/src/components/chatbi/SavedReportQuickViews.vue                      |   74 +++
 frontend/src/components/chatbi/SavedReportResultTable.vue                     |   90 +++
 frontend/src/components/data-portal/DataPortalReportCreateModal.vue           | 1415 +++++++++++++++++++++++++++++++++++++++++++++++
 frontend/src/components/data-portal/DataPortalReportSection.vue               |  277 +++++++++-
 frontend/src/components/data-portal/SqlCodeViewer.vue                         |  113 ++++
 frontend/src/components/embed/BrowserPanel.vue                                |  780 ++++++++++++++++++++++----
 frontend/src/components/example/ExampleFlowGuideBanner.vue                    |  265 +++++++++
 frontend/src/components/knowledge/KnowledgeFlowGuideBanner.vue                |  302 ++++++++++
 frontend/src/components/mcp/McpFlowGuideBanner.vue                            |  276 +++++++++
 frontend/src/components/metadata/MetadataFlowGuideBanner.vue                  |  239 ++++++++
 frontend/src/components/metadata/RelationshipList.vue                         |  290 +---------
 frontend/src/components/metadata/SmartImportWizard.vue                        |   16 +-
 frontend/src/components/metadata/SmartMetricModal.vue                         |  844 +++++++++++++++++++++++++---
 frontend/src/components/metadata/SmartRelationshipModal.vue                   | 1180 +++++++++++++++++++++++++++++++++++++++
 frontend/src/components/skill/SkillFlowGuideBanner.vue                        |  267 +++++++++
 frontend/src/components/system/McpServerRegistry.vue                          |   11 +
 frontend/src/components/system/ModelRegistry.vue                              |   68 ++-
 frontend/src/components/task/TaskFlowGuideBanner.vue                          |  274 +++++++++
 frontend/src/composables/chat/useSavedReportWorkflow.ts                       |   50 +-
 frontend/src/composables/useDataPortalHome.ts                                 |   49 +-
 frontend/src/utils/processTimeline.ts                                         |   70 +++
 frontend/src/utils/savedReportDefaults.ts                                     |   44 +-
 frontend/src/utils/savedReportOpenProtocol.ts                                 |    3 +
 frontend/src/views/AgentDebug.vue                                             |  101 ++--
 frontend/src/views/AgentManagement.vue                                        |  305 ++++++++--
 frontend/src/views/Chat.vue                                                   |    2 +
 frontend/src/views/DataPortalHome.vue                                         |  477 ++++++++++++++--
 frontend/src/views/DataSourceManagement.vue                                   |  139 ++++-
 frontend/src/views/EmbedChat.vue                                              |  318 ++++++-----
 frontend/src/views/ExampleManagement.vue                                      |  265 ++++++++-
 frontend/src/views/KnowledgeBaseManagement.vue                                |  296 +++++++++-
 frontend/src/views/McpManagement.vue                                          |  273 ++++++++-
 frontend/src/views/MemoryManagement.vue                                       |  154 ++++++
 frontend/src/views/MetadataDatasets.vue                                       |  191 ++++++-
 frontend/src/views/MetadataTables.vue                                         |   22 +-
 frontend/src/views/PersonalCenter.vue                                         |   98 +++-
 frontend/src/views/PromptStudio.vue                                           |  142 +++++
 frontend/src/views/SkillsManagement.vue                                       |  418 +++++++++-----
 frontend/src/views/SystemConfig.vue                                           |  196 ++++++-
 frontend/src/views/TaskCenter.vue                                             |  360 ++++++++----
 k8s_deploy/.gitignore                                                         |    6 +
 k8s_deploy/README.md                                                          |  396 +++++++++++++
 k8s_deploy/configmap.yaml                                                     |   39 ++
 k8s_deploy/deployment.yaml                                                    |   76 +++
 k8s_deploy/ingress.example.yaml                                               |   38 ++
 k8s_deploy/kustomization.yaml                                                 |   16 +
 k8s_deploy/namespace.yaml                                                     |    6 +
 k8s_deploy/pvc.yaml                                                           |   16 +
 k8s_deploy/secret.example.yaml                                                |   24 +
 k8s_deploy/service.yaml                                                       |   17 +
 start-logs.md                                                                 |  293 ++++++++++
 tests/CHECKLIST.md                                                            |   49 +-
 tests/README.md                                                               |   16 +-
 tests/ai/runners/test_knowledge_hallucination_guard.py                        |   45 ++
 tests/ai/runners/test_tool_loop_config_loading.py                             |   41 ++
 tests/ai/runtime/test_agentscope_chat_client.py                               |   45 ++
 tests/ai/runtime/test_agentscope_llm_factory.py                               |  211 +++++++
 tests/ai/runtime/test_agentscope_native_agent.py                              |    8 +
 tests/ai/runtime/test_agentscope_tooling.py                                   |   39 ++
 tests/ai/runtime/test_agentscope_workspace.py                                 |    2 +
 tests/ai/runtime/test_process_timeline_snapshot.py                            |   28 +
 tests/ai/runtime/test_reasoning_request_config.py                             |   17 +-
 tests/ai/runtime/test_stream_repetition_detector.py                           |  232 ++++++++
 tests/ai/runtime/test_tool_loop_detector.py                                   |   11 +-
 tests/ai/test_agent_readiness.py                                              |   24 +
 tests/ai/test_execution_observability.py                                      |  154 ++++++
 tests/ai/test_knowledge_utils.py                                              |   53 ++
 tests/ai/test_model_call_context_breakdown.py                                 |   60 ++
 tests/ai/test_multi_agent_orchestrator.py                                     |   63 +++
 tests/ai/test_prompt_assembler.py                                             |   27 +
 tests/ai/test_route_progress.py                                               |   72 +++
 tests/ai/test_router_context.py                                               |   71 +++
 tests/ai/test_sub_agent_delegation.py                                         |   24 +
 tests/api/portal/test_saved_report_preview_contract.py                        |  194 +++++++
 tests/api/portal/test_saved_reports.py                                        |  106 +++-
 tests/api/v1/test_browser_sessions.py                                         |   56 ++
 tests/frontend/test_agent_flow_guide_contract.py                              |   43 ++
 tests/frontend/test_browser_panel_contract.py                                 |    2 +-
 tests/frontend/test_chat_sandbox_workspace_contract.py                        |   48 ++
 tests/frontend/test_chat_shared_helpers_behavior.py                           |   93 ++++
 tests/frontend/test_chat_surface_extraction_contract.py                       |   14 +-
 tests/frontend/test_data_portal_home_contract.py                              |    7 +-
 tests/frontend/test_data_portal_report_closure_contract.py                    |  117 ++++
 tests/frontend/test_dataset_menu_loading_contract.py                          |   56 +-
 tests/frontend/test_embed_thought_stages.py                                   |   46 ++
 tests/frontend/test_example_flow_guide_contract.py                            |   40 ++
 tests/frontend/test_knowledge_flow_guide_contract.py                          |   44 ++
 tests/frontend/test_mcp_flow_guide_contract.py                                |   50 ++
 tests/frontend/test_memory_specs_contract.py                                  |   26 +
 tests/frontend/test_metadata_dataset_sort_contract.py                         |   20 +
 tests/frontend/test_metadata_flow_guide_contract.py                           |   39 ++
 tests/frontend/test_model_thinking_config_contract.py                         |   28 +-
 tests/frontend/test_platform_timezone_contract.py                             |    3 +-
 tests/frontend/test_prompt_and_datasource_specs_contract.py                   |   40 ++
 tests/frontend/test_saved_report_editor_unification_contract.py               |   83 +++
 tests/frontend/test_saved_report_source_context.py                            |   72 +++
 tests/frontend/test_saved_report_ui_ux_contract.py                            |  131 +++++
 tests/frontend/test_saved_reports_renaming_and_creation_contract.py           |   63 +++
 tests/frontend/test_skill_flow_guide_contract.py                              |   41 ++
 tests/frontend/test_smart_metric_modal_contract.py                            |   59 ++
 tests/frontend/test_smart_relationship_modal_contract.py                      |   49 ++
 tests/frontend/test_system_config_save_bar_contract.py                        |   33 ++
 tests/frontend/test_task_flow_guide_contract.py                               |   40 ++
 tests/services/ai/test_agent_manager.py                                       |   30 +
 tests/services/ai/test_agent_service_memory_parallel.py                       |   60 ++
 tests/services/ai/test_agent_service_skill_hint.py                            |   35 ++
 tests/services/ai/test_browser_events.py                                      |  119 ++++
 tests/services/ai/test_browser_runtime.py                                     |   44 +-
 tests/services/ai/test_browser_session_service.py                             |   59 ++
 tests/services/ai/test_browser_worker.py                                      |  252 +++++++++
 tests/services/ai/test_memory_service.py                                      |   36 +-
 tests/services/ai/test_route_progress_stream.py                               |   45 ++
 tests/services/ai/test_router_service.py                                      |   76 +++
 tests/services/ai/test_skill_resolver_cache.py                                |  110 ++++
 tests/services/test_metadata_metric_update.py                                 |   58 ++
 tests/services/test_smart_metric_recommend.py                                 |  122 ++++
 tests/services/test_smart_relationship_recommend.py                           |   81 +++
 tests/test_agent_primary_capability_migrations.py                             |   46 ++
 tests/test_db_prod_apply_sql.py                                               |  366 ++++++++++++
 tests/test_dev_sh_python_bootstrap.py                                         |  191 +++++++
 tests/test_model_thinking_schema_contract.py                                  |   61 ++
 219 files changed, 23781 insertions(+), 2215 deletions(-)
 create mode 100644 app/services/ai/route_progress.py
 create mode 100644 app/services/ai/runtime/execution_observability.py
 create mode 100644 app/services/ai/runtime/stream_repetition_detector.py
 create mode 100644 db-prod-pg/V31-add_agent_legacy_primary_capabilities.sql
 create mode 100644 db-prod/V131-add_agent_legacy_primary_capabilities.sql
 create mode 100644 docs/superpowers/plans/2026-08-25-codemirror-sql-editor.md
 create mode 100644 docs/superpowers/plans/2026-08-25-route-progress-sse-display.md
 create mode 100644 docs/superpowers/plans/2026-08-25-saved-report-dynamic-parameter-shortcuts.md
 create mode 100644 docs/superpowers/plans/2026-08-25-unify-saved-report-editor.md
 create mode 100644 docs/superpowers/plans/2026-08-26-agent-execution-latency-optimization.md
 create mode 100644 docs/superpowers/plans/2026-08-26-dev-sh-python-bootstrap.md
 create mode 100644 docs/superpowers/plans/2026-08-26-docker-terminal-welcome-banner.md
 create mode 100644 docs/superpowers/plans/2026-08-26-k8s-deploy.md
 create mode 100644 docs/superpowers/plans/2026-08-26-saved-report-ui-ux.md
 create mode 100644 docs/superpowers/plans/2026-08-26-saved-report-view-switch.md
 create mode 100644 docs/superpowers/plans/2026-08-26-smart-metric-detail.md
 create mode 100644 docs/superpowers/plans/2026-08-26-thinking-tool-choice-fallback.md
 create mode 100644 docs/superpowers/specs/2026-08-25-auto-routing-latency-unification-design.md
 create mode 100644 docs/superpowers/specs/2026-08-25-codemirror-sql-editor-design.md
 create mode 100644 docs/superpowers/specs/2026-08-25-unify-saved-report-editor-design.md
 create mode 100644 docs/superpowers/specs/2026-08-26-dev-sh-python-bootstrap-design.md
 create mode 100644 docs/superpowers/specs/2026-08-26-docker-terminal-welcome-banner-design.md
 create mode 100644 docs/superpowers/specs/2026-08-26-k8s-deploy-design.md
 create mode 100644 docs/superpowers/specs/2026-08-26-saved-report-view-switch-design.md
 create mode 100644 docs/superpowers/specs/2026-08-26-smart-metric-detail-design.md
 create mode 100644 docs/superpowers/specs/2026-08-26-thinking-tool-choice-fallback-design.md
 create mode 100644 frontend/src/components/agent/AgentFlowGuideBanner.vue
 delete mode 100644 frontend/src/components/chat/SavedReportEditorModal.vue
 create mode 100644 frontend/src/components/chatbi/SavedReportQuickViews.vue
 create mode 100644 frontend/src/components/chatbi/SavedReportResultTable.vue
 create mode 100644 frontend/src/components/data-portal/DataPortalReportCreateModal.vue
 create mode 100644 frontend/src/components/data-portal/SqlCodeViewer.vue
 create mode 100644 frontend/src/components/example/ExampleFlowGuideBanner.vue
 create mode 100644 frontend/src/components/knowledge/KnowledgeFlowGuideBanner.vue
 create mode 100644 frontend/src/components/mcp/McpFlowGuideBanner.vue
 create mode 100644 frontend/src/components/metadata/MetadataFlowGuideBanner.vue
 create mode 100644 frontend/src/components/metadata/SmartRelationshipModal.vue
 create mode 100644 frontend/src/components/skill/SkillFlowGuideBanner.vue
 create mode 100644 frontend/src/components/task/TaskFlowGuideBanner.vue
 create mode 100644 k8s_deploy/.gitignore
 create mode 100644 k8s_deploy/README.md
 create mode 100644 k8s_deploy/configmap.yaml
 create mode 100644 k8s_deploy/deployment.yaml
 create mode 100644 k8s_deploy/ingress.example.yaml
 create mode 100644 k8s_deploy/kustomization.yaml
 create mode 100644 k8s_deploy/namespace.yaml
 create mode 100644 k8s_deploy/pvc.yaml
 create mode 100644 k8s_deploy/secret.example.yaml
 create mode 100644 k8s_deploy/service.yaml
 create mode 100644 start-logs.md
 create mode 100644 tests/ai/runners/test_tool_loop_config_loading.py
 create mode 100644 tests/ai/runtime/test_stream_repetition_detector.py
 create mode 100644 tests/ai/test_execution_observability.py
 create mode 100644 tests/ai/test_route_progress.py
 create mode 100644 tests/api/portal/test_saved_report_preview_contract.py
 create mode 100644 tests/frontend/test_agent_flow_guide_contract.py
 create mode 100644 tests/frontend/test_data_portal_report_closure_contract.py
 create mode 100644 tests/frontend/test_example_flow_guide_contract.py
 create mode 100644 tests/frontend/test_knowledge_flow_guide_contract.py
 create mode 100644 tests/frontend/test_mcp_flow_guide_contract.py
 create mode 100644 tests/frontend/test_memory_specs_contract.py
 create mode 100644 tests/frontend/test_metadata_dataset_sort_contract.py
 create mode 100644 tests/frontend/test_metadata_flow_guide_contract.py
 create mode 100644 tests/frontend/test_prompt_and_datasource_specs_contract.py
 create mode 100644 tests/frontend/test_saved_report_editor_unification_contract.py
 create mode 100644 tests/frontend/test_saved_report_source_context.py
 create mode 100644 tests/frontend/test_saved_report_ui_ux_contract.py
 create mode 100644 tests/frontend/test_saved_reports_renaming_and_creation_contract.py
 create mode 100644 tests/frontend/test_skill_flow_guide_contract.py
 create mode 100644 tests/frontend/test_smart_metric_modal_contract.py
 create mode 100644 tests/frontend/test_smart_relationship_modal_contract.py
 create mode 100644 tests/frontend/test_system_config_save_bar_contract.py
 create mode 100644 tests/frontend/test_task_flow_guide_contract.py
 create mode 100644 tests/services/ai/test_agent_service_memory_parallel.py
 create mode 100644 tests/services/ai/test_route_progress_stream.py
 create mode 100644 tests/services/ai/test_skill_resolver_cache.py
 create mode 100644 tests/services/test_metadata_metric_update.py
 create mode 100644 tests/services/test_smart_metric_recommend.py
 create mode 100644 tests/services/test_smart_relationship_recommend.py
 create mode 100644 tests/test_agent_primary_capability_migrations.py
 create mode 100644 tests/test_dev_sh_python_bootstrap.py
root@laplace-app:~/workspace/github/yunshu-ai-agent-platform# 



root@laplace-app:~/workspace/github/yunshu-ai-agent-platform/docker# ./build_linux_x86.sh 1.0.12.0
=== 开始构建 Docker 镜像 ===
项目根目录: /root/workspace/github/yunshu-ai-agent-platform
Dockerfile:   /root/workspace/github/yunshu-ai-agent-platform/docker/Dockerfile
镜像标签:     nanzi-ai-agent:1.0.12.0
tar 输出目录: /root/workspace/github/yunshu-ai-agent-platform/docker/release
目标平台:     linux/amd64 (docker build)
本机架构与目标平台一致，使用 docker build（无需 buildx）
#0 building with "default" instance using docker driver

#1 [internal] load build definition from Dockerfile
#1 transferring dockerfile:
#1 transferring dockerfile: 3.10kB done
#1 DONE 0.7s

#2 [internal] load metadata for docker.io/library/python:3.11-slim
#2 DONE 5.9s

#3 [internal] load metadata for docker.io/library/node:20-slim
#3 DONE 6.6s

#4 [internal] load .dockerignore
#4 transferring context:
#4 transferring context: 573B done
#4 DONE 3.1s

#5 [internal] load build context
#5 DONE 0.0s

#6 [frontend-builder 1/6] FROM docker.io/library/node:20-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0
#6 resolve docker.io/library/node:20-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0
#6 resolve docker.io/library/node:20-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 3.2s done
#6 DONE 3.4s

#5 [internal] load build context
#5 ...

#7 [stage-1 1/8] FROM docker.io/library/python:3.11-slim@sha256:9c900dea9e8fb7e16277c179b555cc72d29a352dbc33cff48ad5a0412fd5bfc7
#7 resolve docker.io/library/python:3.11-slim@sha256:9c900dea9e8fb7e16277c179b555cc72d29a352dbc33cff48ad5a0412fd5bfc7 3.1s done
#7 DONE 3.6s

#7 [stage-1 1/8] FROM docker.io/library/python:3.11-slim@sha256:9c900dea9e8fb7e16277c179b555cc72d29a352dbc33cff48ad5a0412fd5bfc7
#7 DONE 3.6s

#5 [internal] load build context
#5 transferring context:

#5 transferring context: 76.70MB 0.7s done
#5 DONE 3.9s

#8 [frontend-builder 2/6] WORKDIR /app/frontend
#8 CACHED

#9 [stage-1 2/8] WORKDIR /app
#9 CACHED

#10 [stage-1 3/8] RUN apt-get update && apt-get install -y --no-install-recommends     curl     ca-certificates     gnupg     nodejs     npm     telnet     net-tools     iputils-ping     dnsutils     procps     git     jq     unzip     tzdata     netcat-openbsd     && ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime     && echo Asia/Shanghai > /etc/timezone     && (apt-get install -y --no-install-recommends libaio1         || apt-get install -y --no-install-recommends libaio1t64)     && ln -sf /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1 2>/dev/null || true     && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc         | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg     && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main"         > /etc/apt/sources.list.d/mssql-release.list     && apt-get update     && ACCEPT_EULA=Y apt-get install -y --no-install-recommends         unixodbc         unixodbc-dev         msodbcsql18     && rm -rf /var/lib/apt/lists/*
#10 CACHED

#11 [stage-1 4/8] COPY requirements.txt .
#11 CACHED

#12 [stage-1 5/8] RUN --mount=type=cache,target=/root/.cache/pip     pip install --upgrade pip &&     pip install -r requirements.txt
#12 CACHED

#13 [stage-1 6/8] RUN playwright install --with-deps chromium
#13 CACHED

#14 [stage-1 7/8] COPY . .
#14 ...

#15 [frontend-builder 3/6] COPY frontend/package*.json ./
#15 ...

#14 [stage-1 7/8] COPY . .
#14 DONE 12.9s

#15 [frontend-builder 3/6] COPY frontend/package*.json ./
#15 DONE 13.1s

#16 [frontend-builder 4/6] RUN if [ "0" != "1" ]; then npm ci || npm install; fi

#16 23.63 
#16 23.63 added 566 packages, and audited 567 packages in 20s
#16 23.63 
#16 23.63 182 packages are looking for funding
#16 23.63   run `npm fund` for details
#16 23.75 
#16 23.75 43 vulnerabilities (2 low, 17 moderate, 23 high, 1 critical)
#16 23.75 
#16 23.75 To address issues that do not require attention, run:
#16 23.75   npm audit fix
#16 23.75 
#16 23.75 To address all issues (including breaking changes), run:
#16 23.75   npm audit fix --force
#16 23.75 
#16 23.75 Run `npm audit` for details.
#16 23.76 npm notice
#16 23.76 npm notice New major version of npm available! 10.8.2 -> 12.0.2
#16 23.76 npm notice Changelog: https://github.com/npm/cli/releases/tag/v12.0.2
#16 23.76 npm notice To update run: npm install -g npm@12.0.2
#16 23.76 npm notice
#16 DONE 39.8s

#17 [frontend-builder 5/6] COPY frontend/ .
#17 DONE 5.8s

#18 [frontend-builder 6/6] RUN if [ "0" = "1" ]; then       test -f dist/index.html || (echo "ERROR: PREBUILD_FRONTEND=1 但未找到 frontend/dist/index.html，请先在宿主机执行前端构建" && exit 1);       echo "使用宿主机预构建的前端产物";     else       NODE_OPTIONS="--max-old-space-size=3048" VITE_APP_VERSION="1.0.12.0" npx vite build;     fi
#18 6.515 vite v7.3.0 building client environment for production...

#18 [frontend-builder 6/6] RUN if [ "0" = "1" ]; then       test -f dist/index.html || (echo "ERROR: PREBUILD_FRONTEND=1 但未找到 frontend/dist/index.html，请先在宿主机执行前端构建" && exit 1);       echo "使用宿主机预构建的前端产物";     else       NODE_OPTIONS="--max-old-space-size=3048" VITE_APP_VERSION="1.0.12.0" npx vite build;     fi
#18 6.515 vite v7.3.0 building client environment for production...
#18 6.904 transforming...
#18 8.329 Browserslist: browsers data (caniuse-lite) is 8 months old. Please run:
#18 8.329   npx update-browserslist-db@latest
#18 8.329   Why you should do it regularly: https://github.com/browserslist/update-db#readme
#18 66.19 ✓ 10455 modules transformed.
#18 69.10 rendering chunks...
#18 71.77 [plugin vite:reporter] 
#18 71.77 (!) /app/frontend/src/utils/axios.ts is dynamically imported by /app/frontend/src/main.ts but also statically imported by /app/frontend/src/api/agent.ts, /app/frontend/src/api/artifact.ts, /app/frontend/src/api/changelog.ts, /app/frontend/src/api/metadata.ts, /app/frontend/src/api/model.ts, /app/frontend/src/api/portal.ts, /app/frontend/src/api/ragflow.ts, /app/frontend/src/api/task.ts, /app/frontend/src/api/tool.ts, /app/frontend/src/components/PortalNotificationBell.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/TraceLogViewer.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/chatbi/ChatBIMonitorDialog.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/chatbi/DatasetCapabilityMenu.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/chatbi/SavedReportBrowseModal.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/data-portal/DataPortalReportCreateModal.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/data-portal/DataPortalSceneSection.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/embed/AttachmentImageThumb.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/embed/ChatInput.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/embed/ChatSettings.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/embed/McpCascadeMenu.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/embed/MemoryBrowserDrawer.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/embed/SkillCascadeMenu.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/embed/WorkspaceBrowserDrawer.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/embed/WorkspaceDirectorySaveDialog.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/metadata/SmartImportWizard.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/personal/NotificationConfigs.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/personal/PersonalMemoryPanel.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/personal/PersonalTokenUsage.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/system/McpServerRegistry.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/system/McpToolTester.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/system/RedisKeyCleanupModal.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/task/TaskPromptComposer.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/composables/chat/useWorkspaceCanvas.ts, /app/frontend/src/composables/useBranding.ts, /app/frontend/src/composables/useContextUsage.ts, /app/frontend/src/composables/useDataPortalHome.ts, /app/frontend/src/composables/useDatasetPortal.ts, /app/frontend/src/composables/useKnowledgePortal.ts, /app/frontend/src/composables/useTokenQuota.ts, /app/frontend/src/composables/useWorkbenchHome.ts, /app/frontend/src/utils/cancelConversationRun.ts, /app/frontend/src/utils/conversationFinalize.ts, /app/frontend/src/utils/workspaceFilePreview.ts, /app/frontend/src/views/AgentDebug.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/AgentManagement.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/Dashboard.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/DataPortalHome.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/EmbedChat.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/ExampleManagement.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/KnowledgeBaseManagement.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/KnowledgeRetrievalTest.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/MemoryManagement.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/MetadataDatasets.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/NoPermission.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/Overview.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/PersonalCenter.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/PromptStudio.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/SkillsManagement.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/SystemConfig.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/TaskCenter.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/TokenStats.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/WidgetDebugger.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
#18 71.77 
#18 71.77 [plugin vite:reporter] 
#18 71.77 (!) /app/frontend/src/composables/useBranding.ts is dynamically imported by /app/frontend/src/views/SystemConfig.vue?vue&type=script&setup=true&lang.ts but also statically imported by /app/frontend/src/App.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/embed/WelcomeDashboard.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/Dashboard.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/EmbedChat.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/Login.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/PersonalCenter.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/PersonalWorkbench.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/Users.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
#18 71.77 
#18 71.78 [plugin vite:reporter] 
#18 71.78 (!) /app/frontend/src/utils/chartRenderer.ts is dynamically imported by /app/frontend/src/utils/agentscopeSseHandlers.ts but also statically imported by /app/frontend/src/components/MessageRenderer.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/components/embed/CanvasMarkdownRenderer.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/AgentDebug.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/views/EmbedChat.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
#18 71.78 
#18 71.79 [plugin vite:reporter] 
#18 71.79 (!) /app/frontend/src/views/SkillsManagement.vue is dynamically imported by /app/frontend/src/components/embed/PersonalResourcesModal.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/router/index.ts but also statically imported by /app/frontend/src/views/PersonalCenter.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
#18 71.79 
#18 71.79 [plugin vite:reporter] 
#18 71.79 (!) /app/frontend/src/utils/platformTimezone.ts is dynamically imported by /app/frontend/src/main.ts, /app/frontend/src/views/Login.vue?vue&type=script&setup=true&lang.ts but also statically imported by /app/frontend/src/views/TaskCenter.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
#18 71.79 
#18 71.79 [plugin vite:reporter] 
#18 71.79 (!) /app/frontend/src/views/TaskCenter.vue is dynamically imported by /app/frontend/src/components/embed/PersonalResourcesModal.vue?vue&type=script&setup=true&lang.ts, /app/frontend/src/router/index.ts but also statically imported by /app/frontend/src/views/PersonalCenter.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
#18 71.79 
#18 73.44 computing gzip size...
#18 74.06 dist/index.html                                           1.02 kB │ gzip:     0.54 kB
#18 74.06 dist/assets/KaTeX_Size3-Regular-CTq5MqoE.woff             4.42 kB
#18 74.06 dist/assets/KaTeX_Size4-Regular-Dl5lxZxV.woff2            4.93 kB
#18 74.06 dist/assets/KaTeX_Size2-Regular-Dy4dx90m.woff2            5.21 kB
#18 74.06 dist/assets/KaTeX_Size1-Regular-mCD8mA8B.woff2            5.47 kB
#18 74.06 dist/assets/KaTeX_Size4-Regular-BF-4gkZK.woff             5.98 kB
#18 74.06 dist/assets/KaTeX_Size2-Regular-oD1tc_U0.woff             6.19 kB
#18 74.06 dist/assets/KaTeX_Size1-Regular-C195tn64.woff             6.50 kB
#18 74.06 dist/assets/KaTeX_Caligraphic-Regular-Di6jR-x-.woff2      6.91 kB
#18 74.06 dist/assets/KaTeX_Caligraphic-Bold-Dq_IR9rO.woff2         6.91 kB
#18 74.06 dist/assets/KaTeX_Size3-Regular-DgpXs0kz.ttf              7.59 kB
#18 74.06 dist/assets/KaTeX_Caligraphic-Regular-CTRA-rTL.woff       7.66 kB
#18 74.06 dist/assets/KaTeX_Caligraphic-Bold-BEiXGLvX.woff          7.72 kB
#18 74.06 dist/assets/KaTeX_Script-Regular-D3wIWfF6.woff2           9.64 kB
#18 74.06 dist/assets/KaTeX_SansSerif-Regular-DDBCnlJ7.woff2       10.34 kB
#18 74.06 dist/assets/KaTeX_Size4-Regular-DWFBv043.ttf             10.36 kB
#18 74.06 dist/assets/KaTeX_Script-Regular-D5yQViql.woff           10.59 kB
#18 74.06 dist/assets/KaTeX_Fraktur-Regular-CTYiF6lA.woff2         11.32 kB
#18 74.06 dist/assets/KaTeX_Fraktur-Bold-CL6g_b3V.woff2            11.35 kB
#18 74.06 dist/assets/KaTeX_Size2-Regular-B7gKUWhC.ttf             11.51 kB
#18 74.06 dist/assets/KaTeX_SansSerif-Italic-C3H0VqGB.woff2        12.03 kB
#18 74.06 dist/assets/KaTeX_SansSerif-Bold-D1sUS0GD.woff2          12.22 kB
#18 74.06 dist/assets/KaTeX_Size1-Regular-Dbsnue_I.ttf             12.23 kB
#18 74.06 dist/assets/KaTeX_SansSerif-Regular-CS6fqUqJ.woff        12.32 kB
#18 74.06 dist/assets/KaTeX_Caligraphic-Regular-wX97UBjC.ttf       12.34 kB
#18 74.06 dist/assets/KaTeX_Caligraphic-Bold-ATXxdsX0.ttf          12.37 kB
#18 74.06 dist/assets/KaTeX_Fraktur-Regular-Dxdc4cR9.woff          13.21 kB
#18 74.06 dist/assets/KaTeX_Fraktur-Bold-BsDP51OF.woff             13.30 kB
#18 74.06 dist/assets/KaTeX_Typewriter-Regular-CO6r4hn1.woff2      13.57 kB
#18 74.06 dist/assets/KaTeX_SansSerif-Italic-DN2j7dab.woff         14.11 kB
#18 74.06 dist/assets/KaTeX_SansSerif-Bold-DbIhKOiC.woff           14.41 kB
#18 74.06 dist/assets/KaTeX_Typewriter-Regular-C0xS9mPB.woff       16.03 kB
#18 74.06 dist/assets/KaTeX_Math-BoldItalic-CZnvNsCZ.woff2         16.40 kB
#18 74.06 dist/assets/KaTeX_Math-Italic-t53AETM-.woff2             16.44 kB
#18 74.06 dist/assets/KaTeX_Script-Regular-C5JkGWo-.ttf            16.65 kB
#18 74.06 dist/assets/KaTeX_Main-BoldItalic-DxDJ3AOS.woff2         16.78 kB
#18 74.06 dist/assets/KaTeX_Main-Italic-NWA7e6Wa.woff2             16.99 kB
#18 74.06 dist/assets/KaTeX_Math-BoldItalic-iY-2wyZ7.woff          18.67 kB
#18 74.06 dist/assets/KaTeX_Math-Italic-DA0__PXp.woff              18.75 kB
#18 74.06 dist/assets/KaTeX_Main-BoldItalic-SpSLRI95.woff          19.41 kB
#18 74.06 dist/assets/KaTeX_SansSerif-Regular-BNo7hRIc.ttf         19.44 kB
#18 74.06 dist/assets/KaTeX_Fraktur-Regular-CB_wures.ttf           19.57 kB
#18 74.06 dist/assets/KaTeX_Fraktur-Bold-BdnERNNW.ttf              19.58 kB
#18 74.06 dist/assets/KaTeX_Main-Italic-BMLOBm91.woff              19.68 kB
#18 74.06 dist/assets/KaTeX_SansSerif-Italic-YYjJ1zSn.ttf          22.36 kB
#18 74.06 dist/assets/KaTeX_SansSerif-Bold-CFMepnvq.ttf            24.50 kB
#18 74.06 dist/assets/KaTeX_Main-Bold-Cx986IdX.woff2               25.32 kB
#18 74.06 dist/assets/KaTeX_Main-Regular-B22Nviop.woff2            26.27 kB
#18 74.06 dist/assets/KaTeX_Typewriter-Regular-D3Ib7_Hf.ttf        27.56 kB
#18 74.06 dist/assets/KaTeX_AMS-Regular-BQhdFMY1.woff2             28.08 kB
#18 74.06 dist/assets/KaTeX_Main-Bold-Jm3AIy58.woff                29.91 kB
#18 74.06 dist/assets/KaTeX_Main-Regular-Dr94JaBh.woff             30.77 kB
#18 74.06 dist/assets/KaTeX_Math-BoldItalic-B3XSjfu4.ttf           31.20 kB
#18 74.06 dist/assets/KaTeX_Math-Italic-flOr_0UB.ttf               31.31 kB
#18 74.06 dist/assets/KaTeX_Main-BoldItalic-DzxPMmG6.ttf           32.97 kB
#18 74.06 dist/assets/KaTeX_AMS-Regular-DMm9YOAa.woff              33.52 kB
#18 74.06 dist/assets/KaTeX_Main-Italic-3WenGoN9.ttf               33.58 kB
#18 74.06 dist/assets/KaTeX_Main-Bold-waoOVXN0.ttf                 51.34 kB
#18 74.06 dist/assets/KaTeX_Main-Regular-ypZvNtVU.ttf              53.58 kB
#18 74.06 dist/assets/KaTeX_AMS-Regular-DRggAlZN.ttf               63.63 kB
#18 74.06 dist/assets/EmbedLayout-KnsO1mLS.css                      0.07 kB │ gzip:     0.09 kB
#18 74.06 dist/assets/KnowledgeMetrics-D6YAjViR.css                 0.07 kB │ gzip:     0.08 kB
#18 74.06 dist/assets/ExampleManagement-B1NmZElV.css                0.12 kB │ gzip:     0.11 kB
#18 74.06 dist/assets/Chat-DGF8WCW8.css                             0.14 kB │ gzip:     0.12 kB
#18 74.06 dist/assets/DataSourceManagement-CRAIa7O3.css             0.17 kB │ gzip:     0.13 kB
#18 74.06 dist/assets/KnowledgeBaseManagement-BgGHe52o.css          0.27 kB │ gzip:     0.16 kB
#18 74.06 dist/assets/KnowledgeRetrievalTest-BTv9WpvT.css           1.14 kB │ gzip:     0.36 kB
#18 74.06 dist/assets/EmbedChat-CgyS0Ty0.css                       22.11 kB │ gzip:     4.09 kB
#18 74.06 dist/assets/index-K3psCyJS.css                          640.75 kB │ gzip:    98.31 kB
#18 74.06 dist/assets/McpManagement-mF6hABA4.js                     0.06 kB │ gzip:     0.08 kB
#18 74.06 dist/assets/PersonalMemoryPanel-BRcGbHtC.js               0.06 kB │ gzip:     0.08 kB
#18 74.06 dist/assets/PersonalTokenUsage-DAeq4ibW.js                0.06 kB │ gzip:     0.08 kB
#18 74.06 dist/assets/DataPortalHome-DeLcqpiF.js                    0.06 kB │ gzip:     0.08 kB
#18 74.06 dist/assets/clone-YssqY8qt.js                             0.09 kB │ gzip:     0.11 kB
#18 74.06 dist/assets/channel-B4DlXgTr.js                           0.11 kB │ gzip:     0.12 kB
#18 74.06 dist/assets/init-Gi6I4Gst.js                              0.15 kB │ gzip:     0.13 kB
#18 74.06 dist/assets/chunk-QZHKN3VN-CLTtDvPR.js                    0.19 kB │ gzip:     0.16 kB
#18 74.06 dist/assets/chunk-4BX2VUAB-29OI_uKW.js                    0.22 kB │ gzip:     0.17 kB
#18 74.06 dist/assets/chunk-55IACEB6-Cnhc0z-6.js                    0.22 kB │ gzip:     0.20 kB
#18 74.06 dist/assets/CollectionSync.vue-qOnA5Ymp.js                0.27 kB │ gzip:     0.23 kB
#18 74.06 dist/assets/CollectionCookies.vue-R3LqoRfn.js             0.28 kB │ gzip:     0.23 kB
#18 74.06 dist/assets/CollectionScripts.vue-Dr0rwVd4.js             0.28 kB │ gzip:     0.23 kB
#18 74.06 dist/assets/ViewLayoutContent.vue-Bs7nIF72.js             0.31 kB │ gzip:     0.23 kB
#18 74.06 dist/assets/EmbedLayout-BTvJYUnb.js                       0.33 kB │ gzip:     0.26 kB
#18 74.06 dist/assets/use-tree-walker-oIfnraJn.js                   0.33 kB │ gzip:     0.27 kB
#18 74.06 dist/assets/ViewLayout.vue-BVvNE0aq.js                    0.34 kB │ gzip:     0.26 kB
#18 74.06 dist/assets/stateDiagram-v2-4FDKWEC3-Dh2osyQP.js          0.36 kB │ gzip:     0.27 kB
#18 74.06 dist/assets/chunk-FMBD7UC4-mEyfBmVQ.js                    0.36 kB │ gzip:     0.26 kB
#18 74.06 dist/assets/ArrowLeftIcon-CDbWIXBo.js                     0.36 kB │ gzip:     0.28 kB
#18 74.06 dist/assets/classDiagram-2ON5EDUG-BPlqted3.js             0.40 kB │ gzip:     0.28 kB
#18 74.06 dist/assets/classDiagram-v2-WZHVMYZB-BPlqted3.js          0.40 kB │ gzip:     0.28 kB
#18 74.06 dist/assets/chunk-QN33PNHL-C7mVPRxj.js                    0.50 kB │ gzip:     0.35 kB
#18 74.06 dist/assets/EditSidebarListElement.vue-C19jicTZ.js        0.53 kB │ gzip:     0.36 kB
#18 74.06 dist/assets/ViewLayoutSection.vue-B4HRHPYt.js             0.55 kB │ gzip:     0.39 kB
#18 74.06 dist/assets/min-BFKvXqYe.js                               0.59 kB │ gzip:     0.36 kB
#18 74.06 dist/assets/infoDiagram-WHAUD3N6-Bj9x1yT5.js              0.62 kB │ gzip:     0.42 kB
#18 74.06 dist/assets/ScalarAsciiArt.vue-BfxEnFvH.js                0.96 kB │ gzip:     0.61 kB
#18 74.06 dist/assets/ScalarHotkey.vue-C0JZ7yh7.js                  1.13 kB │ gzip:     0.71 kB
#18 74.06 dist/assets/ordinal-Cboi1Yqb.js                           1.19 kB │ gzip:     0.57 kB
#18 74.06 dist/assets/chunk-TZMSLE5B-DvOVhxNA.js                    1.43 kB │ gzip:     0.63 kB
#18 74.06 dist/assets/Form.vue-DdZiQxRn.js                          1.52 kB │ gzip:     0.84 kB
#18 74.06 dist/assets/CollectionAuthentication.vue-LcOeF365.js      1.57 kB │ gzip:     0.84 kB
#18 74.06 dist/assets/DeleteSidebarListElement.vue-DuW733dL.js      1.59 kB │ gzip:     0.87 kB
#18 74.06 dist/assets/EmptyState.vue-CIVmieYt.js                    1.87 kB │ gzip:     0.65 kB
#18 74.06 dist/assets/Draggable.vue-B3Gt_vM6.js                     1.93 kB │ gzip:     1.03 kB
#18 74.06 dist/assets/CommandActionInput.vue-CQ_8appJ.js            1.94 kB │ gzip:     1.05 kB
#18 74.06 dist/assets/useWorkbenchHome-BJcMl8HA.js                  2.35 kB │ gzip:     1.27 kB
#18 74.06 dist/assets/SidebarButton.vue-BmtqEqor.js                 2.64 kB │ gzip:     1.38 kB
#18 74.06 dist/assets/CollectionOverview.vue-BdT3itmN.js            3.00 kB │ gzip:     1.35 kB
#18 74.06 dist/assets/CollectionSettings.vue-DIMbDZZd.js            3.07 kB │ gzip:     1.50 kB
#18 74.06 dist/assets/arc-B5zgEUl4.js                               3.43 kB │ gzip:     1.47 kB
#18 74.06 dist/assets/Chat-B-xhrFXE.js                              3.76 kB │ gzip:     1.84 kB
#18 74.06 dist/assets/DataTableHeader.vue-CH_TpCJ0.js               3.82 kB │ gzip:     1.45 kB
#18 74.06 dist/assets/CollectionServers.vue-Cdn0FlAF.js             3.90 kB │ gzip:     1.82 kB
#18 74.06 dist/assets/SidebarListElement.vue-CmViANWl.js            4.08 kB │ gzip:     1.71 kB
#18 74.06 dist/assets/diagram-S2PKOQOG-aTAuyKNR.js                  4.24 kB │ gzip:     1.85 kB
#18 74.06 dist/assets/defaultLocale-DX6XiGOO.js                     4.69 kB │ gzip:     2.18 kB
#18 74.06 dist/assets/Cookies.vue-ByzgLIEW.js                       4.85 kB │ gzip:     2.08 kB
#18 74.06 dist/assets/Collection.vue-ObeCeAQg.js                    4.94 kB │ gzip:     2.14 kB
#18 74.06 dist/assets/pieDiagram-ADFJNKIX-sswWPwc9.js               5.18 kB │ gzip:     2.29 kB
#18 74.06 dist/assets/linear-7Qx1h_Rx.js                            5.65 kB │ gzip:     2.31 kB
#18 74.06 dist/assets/diagram-QEK2KX5R-CyvoDuR2.js                  5.85 kB │ gzip:     2.47 kB
#18 74.06 dist/assets/EnvironmentModal.vue-BoZ_cucp.js              6.17 kB │ gzip:     2.34 kB
#18 74.06 dist/assets/ScenarioTemplateDetail-ytoxfe7p.js            6.51 kB │ gzip:     2.56 kB
#18 74.06 dist/assets/IconSelector.vue-CZKuzkwu.js                  7.64 kB │ gzip:     3.15 kB
#18 74.06 dist/assets/_baseUniq-UeAHn3lU.js                         8.48 kB │ gzip:     3.53 kB
#18 74.06 dist/assets/Environment.vue-DnaTP-r2.js                   8.74 kB │ gzip:     3.39 kB
#18 74.06 dist/assets/Settings.vue-yXWNCCwO.js                      8.75 kB │ gzip:     2.72 kB
#18 74.06 dist/assets/graph-DLxSxpD6.js                             9.36 kB │ gzip:     3.20 kB
#18 74.06 dist/assets/CollectionEnvironment.vue-eNoXznKr.js         9.45 kB │ gzip:     3.43 kB
#18 74.06 dist/assets/stateDiagram-FKZM4ZOC-CicKwdhN.js            10.35 kB │ gzip:     3.62 kB
#18 74.06 dist/assets/ScenarioTemplates-B56jH8m7.js                10.72 kB │ gzip:     3.67 kB
#18 74.06 dist/assets/dagre-6UL2VRFP-Bc_T1P3L.js                   10.96 kB │ gzip:     4.09 kB
#18 74.06 dist/assets/KnowledgeMetrics-BvA7jllf.js                 12.07 kB │ gzip:     4.34 kB
#18 74.06 dist/assets/mediaTypes-Chzu5fuj.js                       15.46 kB │ gzip:     3.73 kB
#18 74.06 dist/assets/diagram-PSM6KHXK-DVPxDUHs.js                 15.80 kB │ gzip:     5.65 kB
#18 74.06 dist/assets/TokenStats-DRIdxwDu.js                       15.92 kB │ gzip:     5.08 kB
#18 74.06 dist/assets/ScenarioTemplateInstall-5vQimlf0.js          16.95 kB │ gzip:     5.40 kB
#18 74.06 dist/assets/kanban-definition-3W4ZIXB7-D0xEOSx4.js       20.17 kB │ gzip:     7.15 kB
#18 74.06 dist/assets/mindmap-definition-VGOIOE7T-DyJe1ebm.js      20.88 kB │ gzip:     7.27 kB
#18 74.06 dist/assets/sankeyDiagram-TZEHDZUN-DVatg6E1.js           22.08 kB │ gzip:     8.12 kB
#18 74.06 dist/assets/RequestAuth.vue-4_768Ecx.js                  22.26 kB │ gzip:     6.86 kB
#18 74.06 dist/assets/journeyDiagram-XKPGCS4Q-BJYC-16a.js          23.51 kB │ gzip:     8.31 kB
#18 74.06 dist/assets/timeline-definition-IT6M3QCI-kCbXIjPT.js     23.56 kB │ gzip:     8.21 kB
#18 74.06 dist/assets/KnowledgeRetrievalTest-C0B7GfuG.js           24.00 kB │ gzip:     6.87 kB
#18 74.06 dist/assets/gitGraphDiagram-NY62KEGX-8SK_rKUu.js         24.07 kB │ gzip:     7.41 kB
#18 74.06 dist/assets/erDiagram-Q2GNP2WA-Su97QWDc.js               25.21 kB │ gzip:     8.82 kB
#18 74.06 dist/assets/layout-6AQ08QKf.js                           29.28 kB │ gzip:    10.52 kB
#18 74.06 dist/assets/requirementDiagram-UZGBJVZJ-M1ouqj6K.js      30.05 kB │ gzip:     9.41 kB
#18 74.06 dist/assets/PersonalWorkbench-BtyjT-kB.js                30.29 kB │ gzip:     8.18 kB
#18 74.06 dist/assets/quadrantDiagram-AYHSOK5B-Dyl05HJs.js         33.81 kB │ gzip:     9.94 kB
#18 74.06 dist/assets/chunk-DI55MBZ5-BmVyPAhX.js                   36.33 kB │ gzip:    11.85 kB
#18 74.06 dist/assets/WidgetDebugger-PDVnXGof.js                   37.90 kB │ gzip:    13.41 kB
#18 74.06 dist/assets/xychartDiagram-PRI3JC2R-LDLKwCAt.js          40.18 kB │ gzip:    11.43 kB
#18 74.06 dist/assets/RequestRoot.vue-CbPJOdWz.js                  44.93 kB │ gzip:    15.35 kB
#18 74.06 dist/assets/chunk-B4BG7PRW-B_yaLHIy.js                   45.31 kB │ gzip:    14.71 kB
#18 74.06 dist/assets/Roles-tP1QtrmY.js                            50.14 kB │ gzip:    13.25 kB
#18 74.06 dist/assets/MemoryManagement-vAWfdiS-.js                 57.12 kB │ gzip:    16.30 kB
#18 74.06 dist/assets/ExampleManagement-Dh_GGtld.js                57.14 kB │ gzip:    18.34 kB
#18 74.06 dist/assets/flowDiagram-NV44I4VS-BaMAs8z6.js             60.42 kB │ gzip:    19.43 kB
#18 74.06 dist/assets/DataSourceManagement-Btq9sz0N.js             63.03 kB │ gzip:    18.87 kB
#18 74.06 dist/assets/ganttDiagram-JELNMOA3-D-naUp8r.js            68.27 kB │ gzip:    23.13 kB
#18 74.06 dist/assets/c4Diagram-YG6GDRKO-CbWzYjEz.js               70.10 kB │ gzip:    19.67 kB
#18 74.06 dist/assets/blockDiagram-VD42YOAC-BcLPm_eu.js            71.75 kB │ gzip:    20.49 kB
#18 74.06 dist/assets/cose-bilkent-S5V4N54A-W36fJ_37.js            81.66 kB │ gzip:    22.45 kB
#18 74.06 dist/assets/sequenceDiagram-WL72ISMW-DxkkcFsZ.js         97.78 kB │ gzip:    26.85 kB
#18 74.06 dist/assets/Request.vue-BxSf4xm4.js                     102.83 kB │ gzip:    29.53 kB
#18 74.06 dist/assets/KnowledgeBaseManagement-DcVhNtjd.js         110.50 kB │ gzip:    30.30 kB
#18 74.06 dist/assets/architectureDiagram-VXUJARFQ-nCVC3dNT.js    148.46 kB │ gzip:    41.97 kB
#18 74.06 dist/assets/katex-Buwston5.js                           260.49 kB │ gzip:    77.35 kB
#18 74.06 dist/assets/EmbedChat-BscoKHjM.js                       354.89 kB │ gzip:    97.87 kB
#18 74.06 dist/assets/treemap-KMMF4GRG-CXe9siP4.js                373.08 kB │ gzip:    92.29 kB
#18 74.06 dist/assets/cytoscape.esm-DwGIvGbm.js                   441.07 kB │ gzip:   141.26 kB
#18 74.06 dist/assets/index-TtufiHwT.js                         9,075.04 kB │ gzip: 2,652.69 kB
#18 74.06 
#18 74.06 (!) Some chunks are larger than 500 kB after minification. Consider:
#18 74.06 - Using dynamic import() to code-split the application
#18 74.06 - Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
#18 74.06 - Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
#18 74.06 ✓ built in 1m 8s
#18 DONE 76.6s

#19 [stage-1 8/8] COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

#19 [stage-1 8/8] COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist
#19 DONE 5.4s

#20 exporting to image
#20 exporting layers
#20 exporting layers 12.2s done
#20 exporting manifest sha256:c782464e15b4ded1f419ebf0f98e85b2662713470c7f0755ec07794500987d94
#20 exporting manifest sha256:c782464e15b4ded1f419ebf0f98e85b2662713470c7f0755ec07794500987d94 1.1s done
#20 exporting config sha256:64b175163712d02082755c6ca55ecf48048c9af1e19b08052af067db83b83cb4
#20 exporting config sha256:64b175163712d02082755c6ca55ecf48048c9af1e19b08052af067db83b83cb4 0.6s done
#20 exporting attestation manifest sha256:7d55ccc77abf812dd696c7960465081564aba09ca319f73831dd99ad1d739c55
#20 exporting attestation manifest sha256:7d55ccc77abf812dd696c7960465081564aba09ca319f73831dd99ad1d739c55 1.0s done
#20 exporting manifest list sha256:73b9879ab592d134ca7827140bd9c43f0461df360133dd070d34097c647468d0
#20 exporting manifest list sha256:73b9879ab592d134ca7827140bd9c43f0461df360133dd070d34097c647468d0 0.9s done
#20 naming to docker.io/library/nanzi-ai-agent:1.0.12.0
#20 naming to docker.io/library/nanzi-ai-agent:1.0.12.0 0.4s done
#20 unpacking to docker.io/library/nanzi-ai-agent:1.0.12.0
#20 unpacking to docker.io/library/nanzi-ai-agent:1.0.12.0 4.7s done
#20 DONE 21.8s
=== 镜像构建成功: nanzi-ai-agent:1.0.12.0 ===
linux/amd64
镜像架构:     linux/amd64
=== 正在导出镜像到 /root/workspace/github/yunshu-ai-agent-platform/docker/release/nanzi-ai-agent_1.0.12.0_linux-amd64_20260826.tar ===
=== 导出完成 ===


root@laplace-app:~/workspace/github/yunshu-ai-agent-platform/docker# docker image ls | grep nanzi
nanzi-ai-agent:1.0.12.0             73b9879ab592       3.53GB          909MB        
nanzi-api:1.0.3.0                   9c88d5e0f657        491MB          113MB   U    
root@laplace-app:~/workspace/github/yunshu-ai-agent-platform/docker# 




###启动 ###
root@laplace-app:~/workspace/yunshu-aiagent# ll
total 24
drwxr-xr-x  3 root root 4096 Aug 22 22:24 ./
drwxr-xr-x 13 root root 4096 Aug 11 10:38 ../
drwxr-xr-x  9 root root 4096 Aug 19 17:53 data/
-rw-r--r--  1 root root 1974 Aug 22 22:24 docker-compose.ai-agent.yml
-rw-r--r--  1 root root  575 Jul 14 17:22 .env
-rwxrwxrwx  1 root root 1917 Jul 19 11:54 start.sh*
root@laplace-app:~/workspace/yunshu-aiagent# sh start.sh 
-e === 云枢数据服务平台 Docker 启动 ===
-e 停止并删除旧容器...
nanzi-ai-agent
nanzi-ai-agent
-e 启动 AI Agent 容器...
WARN[0000] /root/workspace/yunshu-aiagent/docker-compose.ai-agent.yml: the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion 
[+] up 1/1
 ✔ Container nanzi-ai-agent Started                                                                                               4.3s
-e 等待服务启动并检查依赖连接...
-e 检查数据库连接状态...

-e ✓ 服务启动成功！

服务信息:
  - API 地址: http://localhost:8001
  - API 文档: http://localhost:8001/docs
  - 管理后台: http://localhost:8001/

查看日志: docker logs -f nanzi-ai-agent
停止服务: docker stop nanzi-ai-agent
root@laplace-app:~/workspace/yunshu-aiagent# docker logs -f nanzi-ai-agent
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     ℹ️ Main database configured: DATABASE_TYPE=mysql (effective=mysql)
INFO:     ✅ Database health check passed (via SQLAlchemy Engine)
INFO:     🔌 Connecting to Redis: 10.4.0.107:6359/0
INFO:     ✅ Redis connected successfully
INFO:     🚀 Audit Log Worker started.
INFO:     Initializing Global HTTP Client (Singleton)
INFO:     Scheduler started
INFO:     Added job "_system_audit_log_maintenance_job" to job store "default"
INFO:     Added job "_system_memory_consolidation_job" to job store "default"
INFO:     Added job "_system_knowledge_metrics_sync_job" to job store "default"
DEBUG:     Looking for jobs to run
DEBUG:     Next wakeup is due at 2026-08-27 02:00:00+08:00 (in 10409.978739 seconds)
DEBUG:     Looking for jobs to run
DEBUG:     Next wakeup is due at 2026-08-27 02:00:00+08:00 (in 10409.976286 seconds)
DEBUG:     Looking for jobs to run
DEBUG:     Next wakeup is due at 2026-08-27 02:00:00+08:00 (in 10409.974012 seconds)
DEBUG:     Looking for jobs to run
DEBUG:     Next wakeup is due at 2026-08-27 02:00:00+08:00 (in 10409.971715 seconds)
INFO:     Third-party user sync scheduler: disabled
INFO:     🚀 Agent Task Scheduler started (tz=Asia/Shanghai). Current Scheduler Time: 2026-08-26 23:06:30.033798+08:00
INFO:     Loaded 0 active tasks into scheduler.
INFO:     Loaded 0 active saved report subscriptions into scheduler.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
INFO:     [startup] metadata_provider=ragflow; skip local vector sync
INFO:     [startup] Memory index ready: nanzi:idx:memory:session_summary

```

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
