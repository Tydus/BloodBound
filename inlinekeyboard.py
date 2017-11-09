#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import uuid
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

E={'ok': '⭕️', 'tick': '✔️', 'info': 'ℹ️'}

def _make_keyboard(buttons):
    return InlineKeyboardMarkup([buttons[i : i + 3] for i in range(0, len(buttons), 3)])

def _make_choice_keyboard(id, choices, selection=[], static_buttons=[]):
    ret = []
    for n, i in enumerate(choices):
        text = E['tick'] if n + 1 in selection else i

        ret.append(InlineKeyboardButton(text, callback_data="%s#%d" % (id, n + 1)))

    return _make_keyboard(ret + static_buttons)

class StaticButtonManager:
    def __init__(self):
        self._db = []

    def add(self, text, callback):
        self._db.append({'text': text, 'callback': callback})

    def __call__(self, id):
        ret = []
        for n, i in enumerate(self._db):
            ret.append(InlineKeyboardButton(
                text=i['text'], callback_data='%s#%d' % (id, -n - 1),
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

static_btn_mgr = StaticButtonManager()

class CallbackQueryRouter:
    def __init__(self):
        self._db = {}

    def register_handler(self, message_id, handler):
        self._db[message_id] = handler

    def deregister_handler(self, message_id):
        del self._db[message_id]

    def __call__(self, bot, update):
        print update
        query = update.callback_query
        message = query.message

        try:
            id, choice = query.data.split('#')
            choice = int(choice)
        except Exception as e:
            print e
            return query.answer()

        if choice < 0: # Static buttons
            return static_btn_mgr.handle(bot, update, id, choice)

        handler = self._db.get(message.message_id)
        if not handler:
            return query.answer()
        return handler(bot, update, id, choice)

router = CallbackQueryRouter()

class SingleChoice:
    def __init__(self, bot, original_message, result_callback, candidate, to, blacklist=None, id=None):
        self._callback = result_callback
        self._candidate = candidate
        self._selection = {}
        self._id = str(id or uuid.uuid4())
        self._blacklist = blacklist
        #import pdb; pdb.set_trace()

        if type(to) == list:
            self._to = to
        elif to == None:
            self._to = None
        else:
            self._to = [to]

        reply_markup = _make_choice_keyboard(self._id,
            candidate,
            selection=[],
            static_buttons=static_btn_mgr(self._id),
        )

        bot.edit_message_text(
            text=original_message.text,
            chat_id=original_message.chat_id,
            message_id=original_message.message_id,
            reply_markup=reply_markup,
        )
        router.register_handler(original_message.message_id, self.handle)

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
        ret = self._callback(bot, update, id, username, self.candidate, choice) or {}
        query.answer(**ret)
        return 

class MultipleChoice:
    def __init__(self, bot, original_message, result_callback, candidate, to, id=None):
        self._callback = result_callback
        self._candidate = candidate
        self._selection = {}
        self._id = str(id or uuid.uuid4())
        self._to = to
        self._selections = set()

        reply_markup = _make_choice_keyboard(self._id,
            self._candidate,
            selection=[],
            static_buttons=[self._submit_button()] + static_btn_mgr(self._id),
        )

        bot.edit_message_text(
            text=original_message.text,
            chat_id=original_message.chat_id,
            message_id=original_message.message_id,
            reply_markup=reply_markup,
        )
        router.register_handler(original_message.message_id, self.handle)

    def _submit_button(self):
        return InlineKeyboardButton(E['ok'], callback_data="%s#0" % self._id)

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
            ret = self._callback(bot, update, self._id, self._to, self.candidate, sorted(list(self._selections))) or {}
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
            static_buttons=[self._submit_button()] + static_btn_mgr(self._id),
        )

        bot.edit_message_text(
            text=original_message.text,
            chat_id=original_message.chat_id,
            message_id=original_message.message_id,
            reply_markup=reply_markup,
        )

# Tests

token_list = [
    ["a", "a", "s"], # 0
    ["c", "c", "s"],
    ["w", "w", "s"],
    ["w", "w", "s"],
    ["w", "w", "s"],
    ["c", "c", "s"],
    ["c", "c", "s"],
    ["c", "w", "s"],
    ["c", "w", "s"],
    ["c", "w", "s"]
]

class bb:

    """docstring for bb"""
    def __init__(self, bot, update, chat_id):
        self.chat_id = chat_id
        self.bot = bot
        self.creator = update.message.from_user.username
        self.m = update.message.reply_text("game starting")
        self.players = []
        self.log = []
        self.entry()

    def entry(self):
        SingleChoice(self.bot, self.m, self.entry_cb, ["Enter / Start"], None, blacklist=[], id=self.chat_id)

    def entry_cb(self, bot, update, id, username, candidate, choice):
        import pdb; pdb.set_trace()
        self.players.append(username)
        if username == self.creator: # Game Owner
            bot.edit_message_text(
                text="Game started",
                chat_id=self.m.chat_id,
                message_id=self.m.message_id,
            )
            # self.players.append(self.creator)
            self.prepare_game()
            return 

        # import pdb; pdb.set_trace()
        self.m = bot.edit_message_text(
            text=self.m.text + "\n@%s entered the game" % username,
            chat_id=self.m.chat_id,
            message_id=self.m.message_id,
        )
        s = SingleChoice(bot, self.m, self.entry_cb, ['Enter / Start'], None, blacklist=self.players, id=self.chat_id)

    def shuffle_rank(self):
        count = len(self.players)
        # no 3rd
        redteam = [1]
        blueteam = [1]
        whiteteam = []
        from operator import neg
        import random
        x = range(2, 10)
        random.shuffle(x)
        if count % 2 == 1:
            whiteteam.append(0)
        count -= 1
        redteam += x[:count / 2 - 1]
        random.shuffle(x)
        x.remove(3)
        if 3 not in redteam:
            blueteam += x[:count / 2 - 1]
        else:
            blueteam.append(3)
            blueteam += x[:count / 2 - 2]
        res = map(neg, blueteam) + redteam + whiteteam
        random.shuffle(res)
        print(len(res), res)
        return res

    def prepare_game(self):
        self.player_data = dict()
        # random.shuffle(self.players)
        ranks = self.shuffle_rank()
        for p, r in zip(self.players, ranks):
            self.player_data[p] = {"rank": r, "token": [], "token_available": token_list[abs(r)], "item": []}
        print(self.player_data)
        # self.bm.add(E['info'], self.info_button)
        self.knife = random.randint(0, len(self.players))
        self.round = 1
        self.round_start()
        
    def round_start(self):
        self.log = []
        self.m = bot.edit_message_text(
            text=generate_game_message("%s action" % self.players[self.knife]),
            chat_id=self.m.chat_id,
            message_id=self.m.message_id,
        )
        self.current_candidates = [x[:5] for x in self.players if x != self.players[self.knife]]
        MultipleChoice(bot, self.m, self.attack_cb, [ self.current_candidates + [E["give"]] ], self.players[self.knife], id=self.chat_id)

    def attack_cb(self, bot, update, id, username, candidate, choices):
        message = update.callback_query.message
        if len(choices) == 2:
            pass;
        elif len(choices) == 1 and choices[0] - 1 < len(self.candidates):
            self.victim = self.current_candidates[choices[0] - 1]
            self.log += "%s is attacking %s" % (self.players[self.knife], self.victim)
        else:
            MultipleChoice(bot, self.m, self.attack_cb, [ self.current_candidates + [E["give"]] ], self.players[self.knife], id=self.chat_id)


    def interfere(self):
        self.m = bot.edit_message_text(
            text=generate_game_message("guard %s?" % self.victim),
            chat_id=self.m.chat_id,
            message_id=self.m.message_id,
        )
        self.interfere_candidate = []
        self.blacklist = [self.players[self.knife], self.victim]
        SingleChoice(bot, self.m, self.interfere_cb, [E["interfere"], E["noop"]], self.players, blacklist=self.blacklist, id=self.chat_id)


    def interfere_cb(self, bot, update, id, username, candidate, choice):
        self.blacklist.append(username)
        if choice == 1:
            self.interfere_candidate.append(username)
        self.m = bot.edit_message_text(
            text=self.m.text + "\n@%s chooses %s" % (username, "interfere" if choice == 1 else "noop"),
            chat_id=self.m.chat_id,
            message_id=self.m.message_id
        )

        if set(self.players) - set(self.blacklist) == set():
            interfere_decide()
            return
        SingleChoice(bot, self.m, self.interfere_cb, [E["interfere"], E["noop"]], self.players, blacklist=self.blacklist, id=self.chat_id)


    def interfere_decide(self):
        if len(self.interfere_candidate) == 0:
            attack_result()
        else:
            self.m = bot.edit_message_text(
                text=generate_game_message("accept interfere?"),
                chat_id=self.m.chat_id,
                message_id=self.m.message_id
            )
            SingleChoice(bot, self.m, self.interfere_accept_cb, [self.interfere_candidate + [E["noop"]]], self.victim, id=self.chat_id)

    def interfere_accept_cb(self, bot, update, id, username, candidate, choice):
        if choice - 1 < len(self.interfere_candidate):
            self.log.append("%s accepted %s's interference" % (self.victim, self.interfere_candidate[choice - 1]))
            self.victim = self.interfere_candidate[choice - 1]
        attack_result()

    def attack_result(self):
        self.m = bot.edit_message_text(
                text=generate_game_message("%s select token:" % self.victim),
                chat_id=self.m.chat_id,
                message_id=self.m.message_id
            )
        SingleChoice(bot, self.m, self.attack_result_cb, [E["red"], E["blue"], E["white"], E["skill"]], self.victim, id=self.chat_id)


    def attack_result_cb(self, bot, update, id, username, candidate, choice):
        choices = ["x", "c", "c", "w", "s"]
        redo = False
        if choices[choice] not in self.player_data[username]["token_available"]:
            redo = True
        if choices[choice] == "c":
            if (choice == 2 and self.player_data[username].rank > 0) or (choice == 1 and self.player_data[username].rank < 0):
                redo = True
        if redo:
            self.m = bot.edit_message_text(
                text=generate_game_message("Invalid selection! %s select token:" % self.victim),
                chat_id=self.m.chat_id,
                message_id=self.m.message_id
            )
            SingleChoice(bot, self.m, self.attack_result_cb, [E["red"], E["blue"], E["white"], E["skill"]], self.victim, id=self.chat_id)
        else:
            if len(self.player_data[username]["token_available"]) == 0:
                if abs(self.player_data[username]["rank"]) == 1:
                    if self.player_data[username]["rank"] > 0:
                        game_result("Blue")
                    else:
                        game_result("Red")
                else:
                    if self.player_data[username]["rank"] > 0:
                        game_result("Red")
                    else:
                        game_result("Blue")
            self.player_data[username]["token_available"].remove(choices[choice])
            self.player_data[username]["token"].append(choices[choice])
            round_start()

    def game_result(self, side):
        self.m = bot.edit_message_text(
            text=generate_game_message("%s wins!" % side),
            chat_id=self.m.chat_id,
            message_id=self.m.message_id
        )


    def generate_game_message(self, notice): 
        # log + status + notice
        msg = "round %d\n" % self.round + "\n".join(self.log) + "\n\n"
        for player, data in self.player_data:
            msg += "%s" % (player + "          ")[:5]
            for t in data["token"]:
                if t == "r": msg += E["red"]
                elif t == "b": msg += E["blue"]
                elif t == "w": msg += E["white"]
                else: msg += E[str(abs(data["rank"]))]
            msg += E["empty"] * (3 - len(data["token"]))
            msg += [E[i] for i in data["item"]]
            msg += "\n\n"
        msg += notice

    def info_button(self, bot, update):
        query = update.callback_query
        username = query.from_user.username
        return {
            "text": "test",
            "show_alert": True
        }

        

def info_button(bot, update):
    query = update.callback_query
    username = query.from_user.username

    return {
            'text': u'This is a private info page, exclusive to @%s.\nLegend: 🔪🔴⚪️9️⃣🗡🛡🔒🔑📍' % username,
        'show_alert': True,
    }

def single_choice_cb(bot, update, id, username, candidate, choice):
    message = update.callback_query.message
    bot.edit_message_text(
        text="@%s selected option %s" % (username, choice),
        chat_id=message.chat_id,
        message_id=message.message_id,
    )

def single_choice_test(bot, update):
    username = update.message.from_user.username
    m = update.message.reply_text("%s please select:" % username)
    s = SingleChoice(bot, m, single_choice_cb, ['A', 'B', 'C', 'D'], username)


user_l = ['Nakagawa_Kanon', 'ggplot2', 'harukaff_bot', 'Fake_Byakuya_bot']

def single_choice_group_cb(bot, update, id, username, candidate, choice):
    global user_l
    #import pdb; pdb.set_trace()
    message = update.callback_query.message
    message = bot.edit_message_text(
        text=message.text + "\n@%s selected option %s" % (username, choice),
        chat_id=message.chat_id,
        message_id=message.message_id,
    )
    user_l.remove(username)
    if user_l != []:
        s = SingleChoice(bot, message, single_choice_group_cb, ['A', 'B', 'C', 'D'], user_l, id=id)

def single_choice_group_test(bot, update):
    global user_l
    user_l = ['Nakagawa_Kanon', 'ggplot2', 'harukaff_bot']
    m = update.message.reply_text("%s please select:" % ",".join(user_l))
    s = SingleChoice(bot, m, single_choice_group_cb, ['A', 'B', 'C', 'D'], user_l)

def multiple_choice_cb(bot, update, id, username, candidate, choices):
    message = update.callback_query.message
    bot.edit_message_text(
        text="@%s selected option %s" % (username, ", ".join(map(str, choices))),
        chat_id=message.chat_id,
        message_id=message.message_id,
    )

def multiple_choice_test(bot, update):
    username = update.message.from_user.username
    m = update.message.reply_text("%s please select more than one:" % username)
    s = MultipleChoice(bot, m, multiple_choice_cb, ['A', 'B', 'C', 'D', '1', '2', '3', '4'], username)

blacklist = []

def enter_cb(bot, update, id, username, candidate, choice):
    global blacklist
    message = update.callback_query.message
    if username == message.reply_to_message.from_user.username: # Game Owner
        bot.edit_message_text(
            text="Game started",
            chat_id=message.chat_id,
            message_id=message.message_id,
        )
        return 

    import pdb; pdb.set_trace()
    blacklist.append(username)
    message = bot.edit_message_text(
        text=message.text + "\n@%s entered the game" % username,
        chat_id=message.chat_id,
        message_id=message.message_id,
    )
    s = SingleChoice(bot, message, enter_cb, ['Enter'], None, blacklist=blacklist, id=id)

def enter_test(bot, update):
    username = update.message.from_user.username
    m = update.message.reply_text("%s is calling for players, press button to enter (%s press button to start the game):" % (username, username))
    s = SingleChoice(bot, m, enter_cb, ['Enter'], None)

def help(bot, update):
    update.message.reply_text("Use /start to test this bot.")

def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)

instances = {}

def start_game(bot, update):
    cid = update.message.chat_id
    instances[cid] = bb(bot, update, cid)

def main():
    # Create the Updater and pass it your bot's token.
    updater = Updater("483679321:AAG9x30HL-o4UEIt5dn7tDgYTjsucx2YhWw")

    updater.dispatcher.add_handler(CommandHandler('start', help))
    updater.dispatcher.add_handler(CommandHandler('help', help))
    updater.dispatcher.add_handler(CallbackQueryHandler(router))
    updater.dispatcher.add_handler(CommandHandler('single_choice', single_choice_test))
    updater.dispatcher.add_handler(CommandHandler('single_choice_group', single_choice_group_test))
    updater.dispatcher.add_handler(CommandHandler('multiple_choice', multiple_choice_test))
    updater.dispatcher.add_handler(CommandHandler('enter', enter_test))
    updater.dispatcher.add_handler(CommandHandler('start_game', start_game))
    updater.dispatcher.add_error_handler(error)

    static_btn_mgr.add(E['info'], info_button)
    # Start the Bot
    updater.start_polling()

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()


if __name__ == '__main__':
    main()
