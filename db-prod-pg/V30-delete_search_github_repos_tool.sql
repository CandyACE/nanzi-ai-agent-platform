-- V30: 移除 search_github_repos 通用 API 工具并清理引用
DELETE FROM "sys_api_tools" WHERE "name" = 'search_github_repos';
