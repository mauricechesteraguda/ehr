# type-10022026-Maurice: Multi-stage production React build; no Vite dev server.
FROM node:22.14.0-alpine AS build
WORKDIR /src
COPY package*.json ./
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build
FROM nginx:1.27.4-alpine
COPY web/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /src/dist /usr/share/nginx/html
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/run /etc/nginx
USER nginx
EXPOSE 8080
