#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import uuid
from operator import neg
import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
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

class CallbackQueryRouter:
    def __init__(self):
        self._db = {}
        self._static_db = {}

    def register_handler(self, message_id, handler):
        self._db[message_id] = handler

    def deregister_handler(self, message_id):
        del self._db[message_id]

    def register_static_handler(self, group_id, handler):
        self._static_db[group_id] = handler

    def deregister_static_handler(self, group_id):
        del self._static_db[group_id]

    def __call__(self, bot, update):
        query = update.callback_query
        message = query.message
        print "Answer for message %s from %s: %s" % (
            query.message.message_id,
            query.from_user.username,
            query.data,
        )

        try:
            id, choice = query.data.split('#')
            choice = int(choice)
        except Exception as e:
            print e
            return query.answer()

        if choice < 0: # Static buttons
            handler = self._static_db.get(id)
        else:
            handler = self._db.get(message.message_id)

        if not handler:
            return query.answer()
        return handler(bot, update, id, choice)

router = CallbackQueryRouter()

class SingleChoice:
    def __init__(self, bot, original_message, result_callback, candidate, to, blacklist=None, id=None, text=None, newmessage=False, static_btn_mgr=StaticButtonManager()):
        self._callback = result_callback
        self._candidate = candidate
        self._selection = {}
        self._id = str(id or uuid.uuid4())
        self._blacklist = blacklist
        self._sbm = static_btn_mgr
        self.message = original_message

        if type(to) == list:
            self._to = to
        elif to == None:
            self._to = None
        else:
            self._to = [to]

        reply_markup = _make_choice_keyboard(self._id,
            candidate,
            selection=[],
            static_buttons=self._sbm.buttons(),
        )

        try:
            if newmessage:
                self.message = self.message.reply_text(
                    text=text or self.message.text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
            elif text == None:
                self.message = self.message.edit_reply_markup(
                    reply_markup=reply_markup,
                )
            else: # text != None
                self.message = self.message.edit_text(
                    text=text or original_message.text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
        except:
            pass

        router.register_handler(self.message.message_id, self.handle)

    def handle(self, bot, update, id, choice):
        query = update.callback_query
        username = query.from_user.username

        if self._to and username not in self._to:
            return query.answer()

        if self._blacklist and username in self._blacklist:
            return query.answer()

        if id != self._id:
            return query.answer()

        if choice > len(self._candidate):
            return query.answer()

        if choice == 0: # Submit, not used
            return query.answer()

        router.deregister_handler(query.message.message_id)
        ret = self._callback(bot, update, id, username, self._candidate, choice) or {}
        query.answer(**ret)
        return 

class MultipleChoice:
    def __init__(self, bot, original_message, result_callback, candidate, to, id=None, text=None, newmessage=False, static_btn_mgr=StaticButtonManager()):
        self._callback = result_callback
        self._candidate = candidate
        self._selection = {}
        self._id = str(id or uuid.uuid4())
        self._to = to
        self._selections = set()
        self._sbm = static_btn_mgr
        self.message = original_message

        reply_markup = _make_choice_keyboard(self._id,
            self._candidate,
            selection=[],
            static_buttons=[self._submit_button()] + self._sbm.buttons(),
        )

        try:
            if newmessage:
                self.message = self.message.reply_text(
                    text=text or self.message.text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
            elif text == None:
                self.message = self.message.edit_reply_markup(
                    reply_markup=reply_markup,
                )
            else: # text != None
                self.message = self.message.edit_text(
                    text=text or original_message.text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
        except:
            pass

        router.register_handler(self.message.message_id, self.handle)

    def _submit_button(self):
        return InlineKeyboardButton(u'⭕️', callback_data="%s#0" % self._id)

    def handle(self, bot, update, id, choice):
        query = update.callback_query
        original_message = query.message
        username = query.from_user.username

        if self._to != username:
            return query.answer()

        if id != self._id:
            return query.answer()

        if choice > len(self._candidate):
            return query.answer()

        if choice == 0: # Submit
            router.deregister_handler(original_message.message_id)
            ret = self._callback(bot, update, self._id, self._to, self._candidate, sorted(list(self._selections))) or {}
            query.answer(**ret)
            return

        # toggle choice
        if choice in self._selections:
            self._selections.remove(choice)
        else:
            self._selections.add(choice)
        
        reply_markup = _make_choice_keyboard(self._id,
            self._candidate,
            selection=self._selections,
            static_buttons=[self._submit_button()] + self._sbm.buttons(),
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
        self.instances[cid] = self.game_class(bot, update, cid)

    def start(self, **kwargs):
        self.updater.start_polling(**kwargs)
        self.updater.idle()

    def _error(self, bot, update, error):
        """Log Errors caused by Updates."""
        logger.warning('Update "%s" caused error "%s"', update, error)


__all__ = ['GameManager', 'SingleChoice', 'MultipleChoice', 'StaticButtonManager', 'ParseMode']
