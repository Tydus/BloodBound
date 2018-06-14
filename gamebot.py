#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import uuid
from operator import neg
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

class StaticButtonManager:
    def __init__(self, id=None):
        self._id = str(id or uuid.uuid4())
        self._db = []
        router.register_static_handler(self._id, self.handle)

    def add(self, text, callback):
        self._db.append({'text': text, 'callback': callback})

    def buttons(self):
        ret = []
        for n, i in enumerate(self._db):
            ret.append(InlineKeyboardButton(
                text=i['text'], callback_data='%s#%d' % (self._id, -n - 1),
            ))

        return ret

    def handle(self, bot, update, id, choice):
        query = update.callback_query

        choice = -choice - 1
        if choice >= len(self._db):
            return query.answer()

        return query.answer(
            **self._db[choice]['callback'](bot, update)
        )

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
        if text:
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

        return choice - 1 # choice count from 1

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
        if text:
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
            return map(lambda x: x - 1, selections) # choice count from 1
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


class GameManager:
    def __init__(self, token, game_class, start_game_command="start_game", *args, **kwargs):
        self.updater = Updater(token, *args, **kwargs)
        self.bot = self.updater.bot
        self.game_class = game_class
        self.instances = {}

        self.add_command_handler(start_game_command, self._start_game)
        self.updater.dispatcher.add_handler(CallbackQueryHandler(router))
        self.updater.dispatcher.add_error_handler(self._error)
        
    def add_command_handler(self, cmd, func):
        self.updater.dispatcher.add_handler(CommandHandler(cmd, func))

    def _start_game(self, bot, update):
        cid = update.message.chat_id
        i = self.instances.get(cid)
        if i: i.cancel()
        self.instances[cid] = self.game_class(bot, update, cid, self)

    def start(self, **kwargs):
        self.updater.start_polling(**kwargs)
        self.updater.idle()

    def _error(self, bot, update, error):
        """Log Errors caused by Updates."""
        logger.warning('Update "%s" caused error "%s"', update, error)

    def schedule(self, func, when, context=None):
        return self.updater.job_queue.run_once(func, when, context)

__all__ = ['GameManager', 'SingleChoice', 'MultipleChoice', 'StaticButtonManager', 'ParseMode']
