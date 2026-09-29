# Builds the AI-generated PoC frontend. The generated app has no nginx config
# of its own, so the preview ships one inline: static SPA with /api and /health
# proxied to the generated backend (same contract as the platform frontend).
FROM node:22-alpine AS build

WORKDIR /app
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./
# Canonical build inputs: the platform ships index.html, src/main.tsx,
# vite.config.ts and tsconfig.json so the build works even when the AI omitted
# them (they overwrite anything the model generated; generated code uses plain
# relative imports). Without index.html Vite has no entry module, emits no
# dist/, and the COPY below fails with "stat app/dist: file does not exist".
COPY deploy/frontend/ ./

# The generated package.json decides what npm install fetched, and the model
# routinely omits the build toolchain — vite.config.ts imports
# @vitejs/plugin-react, which npx alone would never resolve. Install it
# explicitly so the preview does not depend on the model getting deps right.
RUN npm install --no-audit --no-fund --no-save \
      vite@^5.4 @vitejs/plugin-react@^4.3 react@^18.3 react-dom@^18.3

# Build with vite directly: esbuild strips TypeScript types without
# type-checking, so model slips like a missing `import React` (tsc TS2503)
# cannot break the preview build. `npm run build` would run tsc first.
RUN npx vite build


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
