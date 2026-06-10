#!/bin/sh
set -eu

cert_dir="/etc/nginx/certs"
letsencrypt_dir="/etc/letsencrypt/live/${DOMAIN}"

(
    current_checksum=""

    while true; do
        if [ -f "$letsencrypt_dir/fullchain.pem" ] && [ -f "$letsencrypt_dir/privkey.pem" ]; then
            new_checksum="$(sha256sum "$letsencrypt_dir/fullchain.pem" | awk '{print $1}')"

            if [ "$new_checksum" != "$current_checksum" ]; then
                ln -sf "$letsencrypt_dir/fullchain.pem" "$cert_dir/fullchain.pem"
                ln -sf "$letsencrypt_dir/privkey.pem" "$cert_dir/privkey.pem"
                current_checksum="$new_checksum"
                nginx -s reload >/dev/null 2>&1 || true
            fi
        fi

        sleep 60
    done
) &
