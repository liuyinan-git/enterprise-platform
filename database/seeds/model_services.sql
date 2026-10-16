-- 模型服务台账种子数据（来源：172.28.110.11 内网盘点 2026-10-16）
-- 执行：mysql -u root -p enterprise_platform < model_services.sql（幂等，可重复执行）
-- 约定：model_code = 容器名（内网唯一标识）；endpoint_url = 服务根地址（不含 /v1）

INSERT IGNORE INTO model_provider (provider_code, provider_name, provider_type, base_url, api_key, enabled)
VALUES ('node1', '内网GPU节点1（8×H20）', 'self_hosted', 'http://172.28.110.11', '', 1);

INSERT IGNORE INTO model_registry
  (model_code, provider_id, model_name, service_type, endpoint_url, probe_method, engine, parameters, enabled)
VALUES
  -- 🟢 活跃
  ('qwen3-embedding-4b', (SELECT id FROM model_provider WHERE provider_code='node1'),
   'Qwen3 Embedding 4B（全场最核心，163k+ 次调用）', 'embedding', 'http://172.28.110.11:8033', 'openai', 'vLLM v0.17.1',
   '{"remark": "调用方：question-bank、cognee-digitalhuman、digital-human-app、8套Dify、外部MCP网关 172.26.98.100/.102 等"}', 1),
  ('BAAIbge-m3', (SELECT id FROM model_provider WHERE provider_code='node1'),
   'BAAI bge-m3（embedding，6k+ 次调用）', 'embedding', 'http://172.28.110.11:8044', 'openai', 'vLLM v0.17.1',
   '{"remark": "调用方：cognee-backend、memory-api-test、172.28.110.13"}', 1),
  ('paddleocr_vlm', (SELECT id FROM model_provider WHERE provider_code='node1'),
   'PaddleOCR VLM（OCR 视觉链路）', 'ocr', 'http://172.28.110.11:6021', 'http', NULL,
   '{"remark": "上游编排：ocr-api(6005)"}', 1),
  ('api_server_qwen2.5_vl', (SELECT id FROM model_provider WHERE provider_code='node1'),
   'Qwen2.5-VL API Server（视觉）', 'vision', 'http://172.28.110.11:6001', 'http', NULL,
   '{"remark": "stdout 空日志属正常（落盘容器内），连接抓包实锤被 ocr-api 调用"}', 1),
  ('voiceprint-api', (SELECT id FROM model_provider WHERE provider_code='node1'),
   '声纹 + ASR（WebSocket）', 'asr', 'http://172.28.110.11:8765', 'tcp', NULL,
   '{"remark": "WebSocket ASR，非 HTTP 标准协议，tcp 探活"}', 1),
  ('qwen38-27b', (SELECT id FROM model_provider WHERE provider_code='node1'),
   'Qwen3.8-27B（独占 GPU1+5）', 'chat', 'http://172.28.110.11:9101', 'openai', 'vLLM v0.28.0',
   '{"remark": "调用方：7套cognee容器、dify-lifangliang、dify-zhangxin；低频（日均约70次），2×H20 过配"}', 1),
  -- 🔴 闲置（待处置）
  ('Qwen3-1.7B', (SELECT id FROM model_provider WHERE provider_code='node1'),
   'Qwen3-1.7B（闲置：0 次调用，建议确认后下线）', 'chat', 'http://172.28.110.11:7102', 'openai', 'vLLM v0.17.1',
   '{"remark": "启动以来 0 次调用"}', 1),
  ('bge-reranker-v2-m3', (SELECT id FROM model_provider WHERE provider_code='node1'),
   'bge-reranker-v2-m3（闲置：仅 2 次调用且 6 周前，建议与 10.30.52.11 负责人确认后下线）', 'rerank', 'http://172.28.110.11:9104', 'tcp', 'vLLM v0.21.0',
   '{"remark": "rerank 接口路径随 vLLM 版本差异，暂用 tcp 探活，回内网验证后可改 openai"}', 1),
  -- 🟡 存疑（日志无输出）
  ('fastwhisper', (SELECT id FROM model_provider WHERE provider_code='node1'),
   'FastWhisper ASR（存疑：7 天无日志，疑似闲置）', 'asr', 'http://172.28.110.11:5014', 'tcp', NULL,
   '{"remark": "容器名 recursing_hamilton，stdout 无日志"}', 1),
  ('api_server_intention_recogntion', (SELECT id FROM model_provider WHERE provider_code='node1'),
   '意图识别服务（存疑：仅服务发现探测）', 'other', 'http://172.28.110.11:8080', 'tcp', NULL,
   '{"remark": "7 天只有 404 探测，无业务请求"}', 1),
  ('stablediffusion', (SELECT id FROM model_provider WHERE provider_code='node1'),
   'Stable Diffusion 文生图（存疑：占位容器）', 'image', 'http://172.28.110.11:6113', 'http', NULL,
   '{"remark": "容器命令 tail -f /dev/null，大概率占位；抓包未见调用"}', 1),
  ('ocr-api', (SELECT id FROM model_provider WHERE provider_code='node1'),
   'OCR 编排层（对外 6005，编排 paddleocr_vlm + qwen2.5_vl）', 'ocr', 'http://172.28.110.11:6005', 'http', NULL,
   '{"remark": "对外 OCR 入口"}', 1);
