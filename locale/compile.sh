#!/bin/bash

for i in */; do
    pushd "$i/LC_MESSAGES"
    msgfmt bot.po -o bot.mo
    popd
done
