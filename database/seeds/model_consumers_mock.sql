-- 本地模拟联调专用：调用方台账种子（仅外网开发机使用；内网部署用 model_consumers.sql）。
-- 前置：已执行 model_services.sql + model_services_mock.sql（台账指向 mock 容器）。
-- 作用：登记 3 个调用方容器（容器名 = 调用方容器的 identifier），关联到 mock 模型，
--       供 collect_model_callers 把 source_ip 反查的容器名匹配上调用方。
-- 幂等：INSERT IGNORE 可重复执行。

INSERT IGNORE INTO model_consumer (consumer_code, consumer_name, identity_type, identifier, contact, remark, evidence)
VALUES
  ('question-bank', '题库服务', 'container', 'question-bank', '', '', 'mock：EMBEDDING_BASE_URL 指向 embedding'),
  ('cognee-backend', 'cognee 后端', 'container', 'cognee-backend', '', '', 'mock：调 chat + reranker'),
  ('memory-api-test', '记忆服务（测试）', 'container', 'memory-api-test', '', '', 'mock：调 chat'),
  ('cognee-digitalhuman', 'cognee 数字人', 'container', 'cognee-digitalhuman', '', '', 'mock：调 embedding + chat');

INSERT IGNORE INTO model_consumer_rel (consumer_id, model_id)
SELECT c.id, m.id FROM model_consumer c, model_registry m
WHERE (c.consumer_code = 'question-bank' AND m.model_code = 'qwen3-embedding-4b')
   OR (c.consumer_code = 'cognee-backend' AND m.model_code IN ('qwen38-27b', 'bge-reranker-v2-m3'))
   OR (c.consumer_code = 'memory-api-test' AND m.model_code = 'qwen38-27b')
   OR (c.consumer_code = 'cognee-digitalhuman' AND m.model_code IN ('qwen3-embedding-4b', 'qwen38-27b'));
