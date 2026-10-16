# 企业全域日志管控与智能告警平台

部署于企业内网的统一日志管控平台，对企业 PC 终端（含双网卡数字员工/RPA 终端）、防火墙、路由器、交换机、内网与外网服务器、应用和数据库等产生的日志进行集中接收、持久化、标准化、安全分析、异常告警与可视化管理。

> 详细设计见《企业全域日志管控与智能告警平台 V1.0 技术设计说明书》（本仓库根目录）。

## 目录结构

- `backend/`：FastAPI 后端（当前实现第一阶段：健康检查、批量日志接收、批次查询）
- `frontend/`：Vue 3 前端（后续阶段实现）
- `nginx/`：反向代理与 HTTPS（后续接入）
- `database/`、`deploy/`、`docs/`：预留目录

## 快速开始（Docker Compose）

```bash
cp .env.example .env      # 修改其中的 CHANGE_ME 占位密钥
docker compose up -d
curl http://localhost:7552/health/ready
```

后端容器启动时会自动执行 `alembic upgrade head` 完成数据库迁移。

## 本地开发（不使用 Docker）

```bash
cd backend
pip install -r requirements.txt
# 需要可用的 MySQL，并按需设置环境变量或 backend/.env
alembic upgrade head
uvicorn app.main:app --reload
```

接口文档：http://localhost:7552/docs
