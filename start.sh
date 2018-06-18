#!/bin/bash

if [ ! "$FQDN" ]; then
    echo 'Warning: $FQDN not present, webhook may not be available.'
    $@
    exit $?
fi

if [ "$WEBHOOK_CERT" ]; then
    echo '$WEBHOOK_CERT present, not making changes on it.'
    $@
    exit $?
fi

EASY_RSA_DIR=/usr/share/easy-rsa

export WEBHOOK_CERT=$EASY_RSA_DIR/keys/$FQDN.crt
export WEBHOOK_KEY=$EASY_RSA_DIR/keys/$FQDN.key

if [ ! -f $CERT_FILE ]; then
    echo "Certificate file $CERT_FILE is not present, so creating one for you!"
    . vars
    ./clean-all
    ./build-ca --batch
    ./build-key-server --batch $FQDN
fi

$@
exit $?
