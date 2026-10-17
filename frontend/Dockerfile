# 前端镜像：Node 构建静态资源，nginx 运行并反代 /enterprise/api
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Vite base 是 /enterprise/，资源实际放在 dist 根目录，因此整体挂到 /enterprise 下
COPY --from=build /app/dist /usr/share/nginx/html/enterprise
EXPOSE 80
