# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
# Build de producción de la SPA, servida por nginx.
# Bases fijadas por digest (ver comentario en Dockerfile.backend).
FROM node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914 AS build
WORKDIR /app
# Cache de capas + cache de BuildKit (--mount=type=cache): mientras
# package-lock.json no cambie, esta capa se reutiliza tal cual. Si cambia,
# npm solo baja los paquetes nuevos/actualizados porque el cache de npm
# persiste entre builds aunque la capa se invalide.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY . .
RUN npm run build

FROM nginx:alpine@sha256:785835ea65db4bba6f021acc0f3be91b0fef76a53fe41f8588c6698d2aed0606
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
