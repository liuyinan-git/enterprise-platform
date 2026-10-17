-- 模型调用方台账种子数据（来源：172.28.110.11 内网盘点 2026-10-16）
-- 执行：见文件尾注（PyMySQL 逐条执行）；幂等可重复执行
-- 说明：MCP 网关两台节点各登记一条，备注注明归属；air_fec_agent 调的 cognee 不在模型台账，不登记关联

INSERT IGNORE INTO model_consumer (consumer_code, consumer_name, identity_type, identifier, contact, remark, evidence)
VALUES
  ('mcp-gw-172.26.98.100', '远程 MCP 网关节点1', 'external_ip', '172.26.98.100', '', '与 172.26.98.102 同属 air_fec_agent 的 GATEWAY_BASE_URL 指向的网关', 'air_fec_agent env 反推；embedding 调用 29,575 次'),
  ('mcp-gw-172.26.98.102', '远程 MCP 网关节点2', 'external_ip', '172.26.98.102', '', '与 172.26.98.100 同属远程 MCP 网关', '日志统计；embedding 调用 647 次'),
  ('biz-172.28.110.13', '局域网业务服务器', 'external_ip', '172.28.110.13', '', 'air_fec_agent 的 intent_ranker_api_url 指向它', '日志统计；embedding 10,517 次 + bge-m3 3,032 次'),
  ('srv-172.28.110.14', '外部服务器（身份待确认）', 'external_ip', '172.28.110.14', '', '身份待确认', '日志统计；embedding 770 次'),
  ('srv-172.28.110.12', '另一台 LLM 服务器', 'external_ip', '172.28.110.12', '', 'air_fec_agent 的 DEEPSEEK_API_URL 指向它', '日志；探活 27b 为主'),
  ('srv-172.28.100.10', '外部服务器（疑似网关/监控）', 'external_ip', '172.28.100.10', '', '身份待确认', '日志；探活 27b + 18 次调用'),
  ('dev-10.30.52.11', '同事机器', 'external_ip', '10.30.52.11', '', 'bge-reranker 唯一调用者，处置前先找负责人确认', 'SSH 来源 + 日志；reranker 仅 2 次（6 周前）'),
  ('question-bank', '题库服务', 'container', 'question-bank', '', '', 'env 实锤：EMBEDDING_BASE_URL=http://172.28.110.11:8033/v1；OCR 走硅基流动云 API'),
  ('cognee-digitalhuman', 'cognee 数字人', 'container', 'cognee-digitalhuman', '', '7 套 cognee 之一', 'env 实锤：配 9101 + 8033'),
  ('cognee-security', 'cognee 安全', 'container', 'cognee-security', '', '7 套 cognee 之一', 'env 实锤：配 9101'),
  ('cognee-lfl', 'cognee lfl', 'container', 'cognee-lfl', '', '7 套 cognee 之一', 'env 实锤：配 9101'),
  ('cognee-lyn', 'cognee lyn', 'container', 'cognee-lyn', '', '7 套 cognee 之一', 'env 实锤：配 9101'),
  ('cognee-fgj', 'cognee fgj', 'container', 'cognee-fgj', '', '7 套 cognee 之一', 'env 实锤：配 9101'),
  ('cognee-zsw', 'cognee zsw', 'container', 'cognee-zsw', '', '7 套 cognee 之一', 'env 实锤：配 9101'),
  ('cognee-trc', 'cognee trc', 'container', 'cognee-trc', '', '7 套 cognee 之一', 'env 实锤：配 9101'),
  ('cognee-backend', 'cognee 后端', 'container', 'cognee-backend', '', '', '日志统计：bge-m3 3,150 次'),
  ('memory-api-test', '记忆服务（测试）', 'container', 'memory-api-test', '', '', 'env 实锤：配 8044'),
  ('digital-human-app', '数字人应用', 'container', 'digital-human-app', '', '', '日志统计：调 8033'),
  ('ocr-api', 'OCR 编排层', 'container', 'ocr-api', '', '对外端口 6005，编排两个视觉服务', '连接抓包实锤：调 6021 + 6001'),
  ('dify-lifangliang', 'Dify（李芳良）', 'external_system', 'dify-lifangliang', '', 'Dify 工作流平台', 'Dify 配置实锤：qwen3.8-27b'),
  ('dify-zhangxin', 'Dify（张鑫）', 'external_system', 'dify-zhangxin', '', 'Dify 工作流平台', 'Dify 配置实锤：qwen3.8-27b');

-- 调用方-模型关联（model_id 经 model_code 子查询解析）
INSERT IGNORE INTO model_consumer_rel (consumer_id, model_id)
SELECT c.id, m.id FROM model_consumer c, model_registry m
WHERE (c.consumer_code = 'mcp-gw-172.26.98.100' AND m.model_code = 'qwen3-embedding-4b')
   OR (c.consumer_code = 'mcp-gw-172.26.98.102' AND m.model_code = 'qwen3-embedding-4b')
   OR (c.consumer_code = 'biz-172.28.110.13' AND m.model_code IN ('qwen3-embedding-4b', 'BAAIbge-m3'))
   OR (c.consumer_code = 'srv-172.28.110.14' AND m.model_code = 'qwen3-embedding-4b')
   OR (c.consumer_code = 'srv-172.28.110.12' AND m.model_code = 'qwen38-27b')
   OR (c.consumer_code = 'srv-172.28.100.10' AND m.model_code = 'qwen38-27b')
   OR (c.consumer_code = 'dev-10.30.52.11' AND m.model_code = 'bge-reranker-v2-m3')
   OR (c.consumer_code = 'question-bank' AND m.model_code = 'qwen3-embedding-4b')
   OR (c.consumer_code = 'cognee-digitalhuman' AND m.model_code IN ('qwen3-embedding-4b', 'qwen38-27b'))
   OR (c.consumer_code = 'cognee-security' AND m.model_code = 'qwen38-27b')
   OR (c.consumer_code = 'cognee-lfl' AND m.model_code = 'qwen38-27b')
   OR (c.consumer_code = 'cognee-lyn' AND m.model_code = 'qwen38-27b')
   OR (c.consumer_code = 'cognee-fgj' AND m.model_code = 'qwen38-27b')
   OR (c.consumer_code = 'cognee-zsw' AND m.model_code = 'qwen38-27b')
   OR (c.consumer_code = 'cognee-trc' AND m.model_code = 'qwen38-27b')
   OR (c.consumer_code = 'cognee-backend' AND m.model_code = 'BAAIbge-m3')
   OR (c.consumer_code = 'memory-api-test' AND m.model_code = 'BAAIbge-m3')
   OR (c.consumer_code = 'digital-human-app' AND m.model_code = 'qwen3-embedding-4b')
   OR (c.consumer_code = 'ocr-api' AND m.model_code IN ('paddleocr_vlm', 'api_server_qwen2.5_vl'))
   OR (c.consumer_code = 'dify-lifangliang' AND m.model_code = 'qwen38-27b')
   OR (c.consumer_code = 'dify-zhangxin' AND m.model_code = 'qwen38-27b');

-- 执行方式（PyMySQL 不支持多语句，需逐条执行，参考 model_services.sql 的方式）：
-- 去注释行 → 按 ; 切分 → 逐条 cursor.execute
