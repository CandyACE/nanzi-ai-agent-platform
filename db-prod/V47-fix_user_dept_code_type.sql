-- V47: Fix User department field and type
-- Rename dept_id to dept_code and change type to VARCHAR to allow non-numeric codes.
-- 幂等：若已改名为 dept_code，再执行会报 1054（Unknown column 'dept_id'），由 apply 脚本忽略。

ALTER TABLE `ai_agent_users` 
CHANGE COLUMN `dept_id` `dept_code` VARCHAR(50) NULL COMMENT '部门代码 (支持字母/数字)';
