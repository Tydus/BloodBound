#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import uuid
import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, Update
from telegram.ext import CallbackQueryHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

def _make_keyboard(buttons):
    return InlineKeyboardMarkup([buttons[i : i + 3] for i in range(0, len(buttons), 3)])

def _make_choice_keyboard(id, choices, selection=[], static_buttons=[]):
    ret = []
    for n, i in enumerate(choices):
        text = u'✔️' if n + 1 in selection else str(i)[:20]

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

    def check_user(_, update):
        query = update.callback_query
        user = query.from_user

        if ((whitelist and user not in whitelist) or
            (blacklist and user     in blacklist)):
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

class Translator:
    def __init__(self):
        self._t = {}
        for i in ['en', 'zh-CN']:
            self._t[i] = gettext.translation(
                'bot', localedir='locale', languages=[i],
            )
        self._t['ja'] = gettext.translation('bot', localedir='locale', languages=['zh-CN'])

        globals()['_'] = self.getText

    # Try to find the `Update` instance within 5 frames
    # Should only be used by _ internally
    def tryFindUpdate(self):
        topframe = inspect.currentframe()
        frame = topframe.f_back
        try:
            for i in range(5):
                frame = frame.f_back
                #dict = frame.f_locals
                dict = inspect.getargvalues(frame)[3]
                for i in dict.values():
                    if type(i) == Update:
                        return i
        except Exception as e:
            return None
        finally:
            del topframe

    # Try to find user's language and translate to that language
    def getText(self, s, override='zh-CN'):
        if override:
            return self._t.get(override, self._t['en']).gettext(s)

        update = self.tryFindUpdate()
        if not update:
            print("Cannot find Update")
            return self._t['en'].gettext(s)

        user = update.effective_user

        print("@%s's language: %s" % (user.username, user.language_code))
        lang = entity.from_user.language_code[:2]
        if lang == 'zh':
            lang = 'zh-CN'
        
        return self._t.get(lang, self._t['en']).gettext(s)

Translator()
