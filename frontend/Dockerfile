FROM node:22-alpine AS build
WORKDIR /web
COPY frontend/package.json ./package.json
COPY frontend/tsconfig.json frontend/vite.config.ts frontend/index.html ./
COPY frontend/src ./src
RUN npm install && npm run build

FROM nginx:1.27-alpine
COPY infra/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80 443
