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
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
