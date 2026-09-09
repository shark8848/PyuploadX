#!/bin/sh
set -e

# Render the portal config template (same PORTAL_API_TOKEN flow as the nginx
# image entrypoint) and start OpenResty in the foreground.
mkdir -p /etc/nginx/conf.d
envsubst '$PORTAL_API_TOKEN' \
    < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

exec openresty -g 'daemon off;'
