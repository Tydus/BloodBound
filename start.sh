#!/bin/bash

if [ ! "$WEBHOOK_FQDN" ]; then
    echo 'Warning: $WEBHOOK_FQDN not present, webhook may not be available.'
    $@
    exit $?
fi

if [ "$WEBHOOK_CERT" ]; then
    echo '$WEBHOOK_CERT present, not making changes on it.'
    $@
    exit $?
fi

export WEBHOOK_CERT=/$WEBHOOK_FQDN.crt
export WEBHOOK_KEY=/$WEBHOOK_FQDN.key

if [ ! -f $WEBHOOK_CERT ]; then
    echo "Certificate file $WEBHOOK_CERT is not present, so creating one for you!"
    openssl req -newkey rsa:2048 -sha256 -nodes -keyout "$WEBHOOK_KEY" -x509 -days 3650 \
        -out "$WEBHOOK_CERT" -subj "/C=NA/ST=NA/L=NA/O=NA/OU=NA/CN=$WEBHOOK_FQDN"
fi

$@
exit $?
