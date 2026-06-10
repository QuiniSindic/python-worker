#!/bin/sh
set -eu

cert_dir="/etc/nginx/certs"
selfsigned_dir="/etc/nginx/selfsigned"
letsencrypt_dir="/etc/letsencrypt/live/${DOMAIN}"

mkdir -p "$cert_dir" "$selfsigned_dir"

if [ ! -f "$selfsigned_dir/fullchain.pem" ] || [ ! -f "$selfsigned_dir/privkey.pem" ]; then
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout "$selfsigned_dir/privkey.pem" \
        -out "$selfsigned_dir/fullchain.pem" \
        -subj "/CN=${DOMAIN}" \
        -addext "subjectAltName=DNS:${DOMAIN}"
fi

if [ -f "$letsencrypt_dir/fullchain.pem" ] && [ -f "$letsencrypt_dir/privkey.pem" ]; then
    ln -sf "$letsencrypt_dir/fullchain.pem" "$cert_dir/fullchain.pem"
    ln -sf "$letsencrypt_dir/privkey.pem" "$cert_dir/privkey.pem"
else
    ln -sf "$selfsigned_dir/fullchain.pem" "$cert_dir/fullchain.pem"
    ln -sf "$selfsigned_dir/privkey.pem" "$cert_dir/privkey.pem"
fi
