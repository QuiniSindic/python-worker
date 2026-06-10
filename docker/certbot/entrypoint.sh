#!/bin/sh
set -eu

if [ "$CERTBOT_STAGING" = "1" ]; then
    staging_arg="--staging"
else
    staging_arg=""
fi

while [ ! -f "/etc/letsencrypt/renewal/${DOMAIN}.conf" ]; do
    certbot certonly \
        --webroot \
        --webroot-path /var/www/certbot \
        --domain "$DOMAIN" \
        --email "$LETSENCRYPT_EMAIL" \
        --agree-tos \
        --no-eff-email \
        --non-interactive \
        $staging_arg && break

    echo "Certificate issuance failed; retrying in 5 minutes."
    sleep 300
done

while true; do
    certbot renew \
        --webroot \
        --webroot-path /var/www/certbot \
        --quiet
    sleep 43200
done
