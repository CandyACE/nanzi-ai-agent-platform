-- V115: 平台时区系统配置（业务时间/调度单一来源，默认 Asia/Shanghai）
INSERT IGNORE INTO `system_configs` (`key`, `value`, `description`, `category`, `is_secret`) VALUES
(
  'platform_timezone',
  'Asia/Shanghai',
  '平台业务时区（IANA）。用于定时任务 Cron、当前时间、相对日期与前端时间展示。修改后立即刷新缓存；运行中的调度器会尝试按新时区重载任务。无法控制的外部 MySQL 服务器时区不受此项影响。',
  'general',
  0
);
