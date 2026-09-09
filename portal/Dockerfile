FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG UPLOAD_API_URL=http://upload-api:8000
ENV UPLOAD_API_URL=$UPLOAD_API_URL
RUN npm run build

# OpenResty (nginx + ngx_lua): nginx-compatible config plus Lua for future
# access control / rate limiting. Unlike the nginx image, the openresty image
# has no auto-envsubst entrypoint, so docker-entrypoint.sh renders the same
# template (PORTAL_API_TOKEN flow) before starting the daemon.
#
# Official OpenResty release series tag (latest 1.31.x build, nginx 1.31 core).
FROM openresty/openresty:1.31-alpine
RUN apk add --no-cache gettext
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.sh /usr/local/bin/portal-entrypoint.sh
RUN chmod +x /usr/local/bin/portal-entrypoint.sh
EXPOSE 80
ENTRYPOINT ["/usr/local/bin/portal-entrypoint.sh"]
