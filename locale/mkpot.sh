#!/bin/bash

pygettext3 -o bot.pot -k "_T" ../*.py

for i in */; do
    pushd "$i/LC_MESSAGES"
    msgmerge bot.po ../../bot.pot > bot.po.new
    mv bot.po.new bot.po
    popd
done
