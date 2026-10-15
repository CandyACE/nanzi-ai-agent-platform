-- V70: 沙箱孤儿对账开关（docker/k8s 均生效）：按容器/Pod 标签回收脱离进程注册表的历史沙箱（PostgreSQL 方言）
INSERT INTO system_configs (key, value, description, category, is_secret) VALUES
(
  'sandbox_orphan_reconcile',
  'true',
  '沙箱孤儿对账开关（docker/k8s 均生效）。开启时后端每约 10 分钟按容器/Pod 的 agentscope.workspace 标签对账，回收「不在本进程注册表中且物理创建超过 30 分钟」的历史沙箱——进程重启或技能集合变更后遗留的容器/Pod 此前永远不会被空闲回收，会以 sleep infinity 永久驻留。注意：注册表是进程内的，单副本部署保持开启；多副本/多 worker 部署必须关闭，否则副本之间会互删正在使用的沙箱。',
  'sandbox',
  FALSE
)
ON CONFLICT (key) DO UPDATE SET
  description = EXCLUDED.description,
  category = EXCLUDED.category;
