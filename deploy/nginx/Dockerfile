# OpenResty production gateway: TLS termination, HTTP->HTTPS redirect, and
# reverse proxy to portal / upload-api. The config is nginx-compatible, so it
# runs unchanged on OpenResty and Lua stays available for future access control.
#
# Official OpenResty release series tag (latest 1.31.x build, nginx 1.31 core).
FROM openresty/openresty:1.31-alpine

# Replace the image's default vhost with the PyUploadX gateway config.
COPY gateway.conf /etc/nginx/conf.d/default.conf

EXPOSE 80 443
