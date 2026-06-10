FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY templates /etc/nginx/templates
COPY entrypoint.d /docker-entrypoint.d

RUN chmod +x /docker-entrypoint.d/*.sh
