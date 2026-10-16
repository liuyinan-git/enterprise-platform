-- 本地模拟联调种子（仅外网开发机使用；内网部署禁止执行，用原版 model_services.sql）。
-- 前置：已执行 model_services.sql（真实台账 12 条已在库）。
-- 作用：
--   1) 5 个代表服务指向本地 mock 容器（deploy/mock-models/，端口 = 10000 + 服务器端口）
--   2) 其余真实条目停用，避免外网探测 172.28.110.11 超时噪音刷健康历史/告警
-- 回切：执行文末「恢复段」。

UPDATE model_registry SET endpoint_url='http://127.0.0.1:18033' WHERE model_code='qwen3-embedding-4b';
UPDATE model_registry SET endpoint_url='http://127.0.0.1:19101' WHERE model_code='qwen38-27b';
UPDATE model_registry SET endpoint_url='http://127.0.0.1:19104' WHERE model_code='bge-reranker-v2-m3';
UPDATE model_registry SET endpoint_url='http://127.0.0.1:18765' WHERE model_code='voiceprint-api';
UPDATE model_registry SET endpoint_url='http://127.0.0.1:16021' WHERE model_code='paddleocr_vlm';

UPDATE model_registry SET enabled=0 WHERE endpoint_url LIKE 'http://172.28.110.11%';

-- ==================== 恢复段（内网部署 / 回切真实环境时执行）====================
-- UPDATE model_registry SET endpoint_url='http://172.28.110.11:8033' WHERE model_code='qwen3-embedding-4b';
-- UPDATE model_registry SET endpoint_url='http://172.28.110.11:9101' WHERE model_code='qwen38-27b';
-- UPDATE model_registry SET endpoint_url='http://172.28.110.11:9104' WHERE model_code='bge-reranker-v2-m3';
-- UPDATE model_registry SET endpoint_url='http://172.28.110.11:8765' WHERE model_code='voiceprint-api';
-- UPDATE model_registry SET endpoint_url='http://172.28.110.11:6021' WHERE model_code='paddleocr_vlm';
-- UPDATE model_registry SET enabled=1 WHERE endpoint_url LIKE 'http://172.28.110.11%';
