#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import uuid
import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
from interactivehandler import InteractiveHandler
import telegram.ext
# from telegram.error import BadRequest

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

def _make_keyboard(buttons):
    return InlineKeyboardMarkup([buttons[i : i + 3] for i in range(0, len(buttons), 3)])

def _make_choice_keyboard(id, choices, selection=[], static_buttons=[]):
    ret = []
    for n, i in enumerate(choices):
        text = u'✔️' if n + 1 in selection else i[:20]

        ret.append(InlineKeyboardButton(text, callback_data="%s#%d" % (id, n + 1)))

    return _make_keyboard(ret + static_buttons)

def single_choice(
    original_message,
    candidate,
    whitelist,
    blacklist=[],
    id=None,
    text=None,
    static_buttons=[],
):
    id = str(id or uuid.uuid4())

    if whitelist and type(whitelist[0]) != int:
        whitelist = map(lambda x: x.id, whitelist)
    if blacklist and type(blacklist[0]) != int:
        blacklist = map(lambda x: x.id, blacklist)

    def check_user(update):
        query = update.callback_query
        uid = query.from_user.user_id

        if ((whitelist and uid not in whitelist) or
           (blacklist and uid in blacklist)):
            query.answer()
            return False

        return True

    reply_markup = _make_choice_keyboard(
        id, candidate, static_buttons=static_buttons,
    )

    try:
        if text and text != original_message.text:
            message = original_message.edit_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        else:
            message = original_message.edit_reply_markup(
                reply_markup=reply_markup,
            )
    except:
        pass

    while True:
        update = yield [CallbackQueryHandler(
            check_user, pattern=r"^" + id + r"#-?[0-9]+$",
        )]

        query = update.callback_query

        choice = int(query.data.split('#')[1])

        if choice > len(candidate) or choice <= 0:
            query.answer()
            continue

        return update, choice - 1 # choice count from 1

def _submit_button(id):
    return InlineKeyboardButton(u'⭕️', callback_data="%s#0" % id)

def multiple_choice(
     original_message,
     candidate,
     to,
     id=None,
     text=None,
     static_buttons=[],
 ):
    id = str(id or uuid.uuid4())

    if type(to) != int:
        to = to.id

    selections = set()

    def check_user(update):
        query = update.callback_query
        uid = query.from_user.user_id

        if uid != to:
            query.answer()
            return False

        return True

    reply_markup = _make_choice_keyboard(id,
        candidate,
        static_buttons=[_submit_button()] + static_buttons,
    )

    try:
        if text and text != original_message.text:
            message = original_message.edit_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        else:
            message = original_message.edit_reply_markup(
                reply_markup=reply_markup,
            )
    except:
        pass

    while True:
        update = yield [CallbackQueryHandler(
            check_user, pattern=r"^" + id + r"#-?[0-9]+$",
        )]

        query = update.callback_query

        choice = int(query.data.split('#')[1])

        if choice > len(candidate) or choice < 0:
            query.answer()
            continue

        if choice == 0: # Submit button
            return update, map(lambda x: x - 1, selections) # choice count from 1
        else:
            # Toggle choice
            if choice in selections:
                selections.remove(choice)
            else:
                selections.add(choice)

        reply_markup = _make_choice_keyboard(id,
            candidate,
            selections=selections,
            static_buttons=[_submit_button()] + static_buttons,
        )

        try:
            self.message = self.message.edit_reply_markup(
                reply_markup=reply_markup,
            )
        except:
            pass

