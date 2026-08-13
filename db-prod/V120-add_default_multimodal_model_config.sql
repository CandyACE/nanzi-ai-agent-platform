-- V120: 系统默认多模态模型（会话模型不支持识图时旁路解析图片）
INSERT IGNORE INTO `system_configs` (`key`, `value`, `description`, `category`, `is_secret`) VALUES
(
  'multimodal_model_name',
  '',
  '系统默认多模态模型。当会话当前模型不支持识图时，用该模型将本轮图片解析为文字后再交给原模型继续回答。留空则提示用户当前模型不支持图片理解。',
  'agent',
  0
);
