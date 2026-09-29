# Builds the AI-generated PoC frontend. The generated app has no nginx config
# of its own, so the preview ships one inline: static SPA with /api and /health
# proxied to the generated backend (same contract as the platform frontend).
FROM node:22-alpine AS build

WORKDIR /app
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./
# Canonical build configs: the platform ships them so the build works even
# when the AI omitted vite.config.ts/tsconfig.json (they overwrite anything
# the model generated; generated code uses plain relative imports).
COPY deploy/frontend/ ./
RUN npm run build


FROM nginx:1.27-alpine AS runtime

RUN printf 'server {\n\
    listen 80;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / { try_files $uri $uri/ /index.html; }\n\
    location /health {\n\
        proxy_pass http://poc-backend:8000/health;\n\
        proxy_set_header Host $host;\n\
    }\n\
    location /api/ {\n\
        proxy_pass http://poc-backend:8000;\n\
        proxy_http_version 1.1;\n\
        proxy_set_header Host $host;\n\
        proxy_read_timeout 300s;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
