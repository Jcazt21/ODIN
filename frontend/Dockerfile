# syntax=docker/dockerfile:1
# Build de producción de la SPA, servida por nginx.
FROM node:20-alpine AS build
WORKDIR /app
# Cache de capas + cache de BuildKit (--mount=type=cache): mientras
# package-lock.json no cambie, esta capa se reutiliza tal cual. Si cambia,
# npm solo baja los paquetes nuevos/actualizados porque el cache de npm
# persiste entre builds aunque la capa se invalide.
COPY package.json package-lock.json ./
# --legacy-peer-deps: openapi-typescript sólo declara peer typescript@^5.x,
# pero el proyecto usa typescript ~6.0.2 (necesario para el resto del código).
# El conflicto es sólo de peer dep en un devDependency usado en un script
# manual (generate:types), no afecta el build real.
RUN --mount=type=cache,target=/root/.npm \
    npm ci --legacy-peer-deps
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/conf.d/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html

# nginx sin privilegios (§5.5 de task.md): el usuario "nginx" ya viene
# creado en la imagen base, solo falta darle permiso de escritura sobre lo
# que el proceso toca en runtime (cache, logs, el conf.d que copiamos como
# root, y el pid file). listen 8080 en nginx.conf porque solo root puede
# bindear puertos <1024 dentro del contenedor.
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d \
    && touch /var/run/nginx.pid \
    && chown nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 8080

# /healthz (nginx.conf) responde 200 sin depender de que el backend esté
# arriba — es liveness del propio nginx, no readiness del stack completo.
# 127.0.0.1 y no localhost: dentro del contenedor "localhost" resuelve a
# ::1 (IPv6, ver /etc/hosts de la imagen base) pero nginx solo escucha en
# 0.0.0.0:8080 (IPv4) — con "localhost" el healthcheck fallaba siempre con
# "connection refused" aunque el servidor respondiera bien.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
