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

E={
   "empty": u"⚫️",
   'ok': u'⭕️',
   'tick': u'✔️',
   'info': u'ℹ️',
   "red": u"🔴",
   "blue": u"🔵",
   "white": u"⚪️",
   "1": u"1️⃣",
   "2": u"2️⃣",
   "3": u"3️⃣",
   "4": u"4️⃣",
   "5": u"5️⃣",
   "6": u"6️⃣",
   "7": u"7️⃣",
   "8": u"8️⃣",
   "9": u"9️⃣",
   "0": u"*️⃣",
   "give": u"↪️",
   "skill": u"💢",
   "interfere": u"⚠️",
   "noop": u"🔜 ",
   "reserved": u"🖌🗡🛡🔱🔰🔮💢♨️㊙️"
}

def _make_keyboard(buttons):
    return InlineKeyboardMarkup([buttons[i : i + 3] for i in range(0, len(buttons), 3)])

def _make_choice_keyboard(id, choices, selection=[], static_buttons=[]):
    ret = []
    for n, i in enumerate(choices):
        text = E['tick'] if n + 1 in selection else i[:20]

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
        self.log = ["Game starting"]
        self.m = update.message.reply_text(self.log[0], parse_mode=ParseMode.HTML,)
        self.players = []
        self.log = []
        self.sbm = StaticButtonManager()
        self.entry()

    def entry(self):
        self.m = SingleChoice(self.bot, self.m, self.entry_cb, ["Enter / Start"], None, blacklist=[], id=self.chat_id, static_btn_mgr=self.sbm).message

    def entry_cb(self, bot, update, id, username, candidate, choice):
        self.players.append(username)
        if username == self.creator: # Game Owner
            self.m.edit_text(
                text="Game started",
                parse_mode=ParseMode.HTML,
            )
            self.prepare_game()
            return 

        self.log.append("@%s entered the game" % username)

        self.m = SingleChoice(
            self.bot, self.m, self.entry_cb,
            ['Enter / Start'],
            None, blacklist=self.players,
            id=self.chat_id,
            static_btn_mgr=self.sbm,
            text="\n".join(self.log)
        ).message

    def shuffle_rank(self):
        count = len(self.players)
        # no 3rd
        redteam = [1]
        blueteam = [1]
        whiteteam = []
        x = range(2, 10)
        random.shuffle(x)
        if count % 2 == 1:
            whiteteam.append(0)
            count -= 1
        if count > 2:
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
            self.player_data[p] = {"rank": r, "token": [], "token_available": token_list[abs(r)][:], "item": []}
        print(self.player_data)
        self.sbm.add(E['info'], self.info_button)
        self.knife = self.players[random.randint(0, len(self.players) - 1)]
        self.round = 0
        self.round_start()
        
    def round_start(self):
        self.round += 1
        self.log = []
        candidate = [x for x in self.players if x != self.knife] + [E['give']]
        self.m = MultipleChoice(
            self.bot, self.m, self.attack_cb,
            candidate,
            self.knife,
            id=self.chat_id,
            static_btn_mgr=self.sbm,
            text=self.generate_game_message("%s action" % self.knife),
            newmessage=True,
        ).message

    def attack_cb(self, bot, update, id, username, candidate, choices):
        message = update.callback_query.message

        try:
            if len(choices) == 0 or len(choices) > 2: 1 / 0

            victim = choices[0] - 1
            if victim >= len(candidate) - 1: 1 / 0 # Don't count "Give"
            victim = candidate[victim]

            if len(choices) == 1: # Attack!
                self.victim = victim
                self.log.append("%s is attacking %s" % (self.knife, self.victim))
                return self.interfere()

            # possibly give knife
            if choices[1] - 1 != len(candidate) - 1: 1 / 0

            old_knife, self.knife = self.knife, victim
            self.log.append("%s gaves the knife to %s." % (old_knife, self.knife))
            self.display_game_message()

            return self.round_start()

        except ZeroDivisionError:
            self.m = MultipleChoice(
                self.bot, self.m, self.attack_cb,
                candidate,
                self.knife,
                id=self.chat_id,
                static_btn_mgr=self.sbm,
                text=self.generate_game_message("%s action invalid, retry:" % self.knife)
            ).message

    def interfere(self):
        self.interfere_candidate = []
        self.blacklist = [self.knife, self.victim]
        for player, data in self.player_data.iteritems():
            if player == self.knife or player == self.victim:
                continue
            if "s" in data["token_available"]:
                self.interfere_candidate.append(player)
            else:
                self.blacklist.append(player)

        if len(self.interfere_candidate) == 0:
            return self.attack_result()

        self.m = SingleChoice(
            self.bot, self.m, self.interfere_cb,
            [E["interfere"], E["noop"]],
            self.interfere_candidate, blacklist=self.blacklist,
            id=self.chat_id,
            static_btn_mgr=self.sbm,
            text=self.generate_game_message("Guard %s?" % self.victim),
        ).message


    def interfere_cb(self, bot, update, id, username, candidate, choice):
        self.blacklist.append(username)
        if choice == 2:
            self.interfere_candidate.remove(username)

        self.log.append("@%s chooses %s" % (username, "interfere" if choice == 1 else "no-op"))

        self.display_game_message()

        if set(self.interfere_candidate) + set(self.blacklist) == set(self.players):
            self.interfere_decide()
            return

        self.m = SingleChoice(
            self.bot, self.m, self.interfere_cb,
            [E["interfere"], E["noop"]],
            self.interfere_candidate, blacklist=self.blacklist,
            id=self.chat_id,
            static_btn_mgr=self.sbm,
        ).message

    def interfere_decide(self):
        if len(self.interfere_candidate) == 0:
            return self.attack_result()
        else:
            self.m = SingleChoice(
                self.bot, self.m, self.interfere_accept_cb,
                self.interfere_candidate + [E["noop"]],
                self.victim,
                id=self.chat_id,
                static_btn_mgr=self.sbm,
                text=self.generate_game_message("accept interfere?"),
            ).message

    def interfere_accept_cb(self, bot, update, id, username, candidate, choice):
        if choice - 1 < len(self.interfere_candidate):
            self.log.append("%s accepted %s's interference" % (self.victim, self.interfere_candidate[choice - 1]))
            self.victim = self.interfere_candidate[choice - 1]
        self.attack_result()

    def attack_result(self):
        if len(self.player_data[self.victim]["token_available"]) == 0:
            if abs(self.player_data[self.victim]["rank"]) == 1:
                if self.player_data[self.victim]["rank"] > 0:
                    return self.game_result(E["blue"])
                else:
                    return self.game_result(E["red"])
            else:
                if self.player_data[self.victim]["rank"] > 0:
                    return self.game_result(E["red"])
                else:
                    return self.game_result(E["blue"])

        self.m = SingleChoice(
            self.bot, self.m, self.attack_result_cb,
            [E["red"], E["blue"], E["white"], E["skill"]],
            self.victim,
            id=self.chat_id,
            static_btn_mgr=self.sbm,
            text=self.generate_game_message("%s select token:" % self.victim),
        ).message

    def attack_result_cb(self, bot, update, id, username, candidate, choice):
        choices = ["x", "c", "c", "w", "s"]
        redo = False
        # import pdb; pdb.set_trace()
        if choices[choice] not in self.player_data[username]["token_available"]:
            redo = True
        if choices[choice] == "c":
            if (choice == 2 and self.player_data[username]["rank"] > 0) or (choice == 1 and self.player_data[username]["rank"] < 0):
                redo = True
        if redo:
            self.m = SingleChoice(
                self.bot, self.m, self.attack_result_cb,
                [E["red"], E["blue"], E["white"], E["skill"]],
                self.victim,
                id=self.chat_id,
                static_btn_mgr=self.sbm,
                text=self.generate_game_message("Invalid selection! %s select token:" % self.victim),
            ).message
        else:
            
            token = self.token_convert_single(self.player_data[self.victim]["rank"], choice)
            self.log.append("%s selected %s token" % (self.victim, token[1]))
            self.display_game_message()
            self.player_data[username]["token_available"].remove(choices[choice])
            self.player_data[username]["token"].append(token[0])
            self.knife = self.victim
            self.debug()
            self.round_start()

    def game_result(self, side):
        self.display_game_message("%s wins!" % side)

    def display_game_message(self, notice=""):
        self.m = self.m.edit_text(
            text=self.generate_game_message(notice),
            parse_mode=ParseMode.HTML,
        )

    def generate_game_message(self, notice=""): 
        # log + status + notice

        l = [u"<b>round %d</b>" % self.round]
        l += self.log
        l.append("")

        for player, data in self.player_data.iteritems():
            ret = "%s" % (player + "             ")[:8]
            for t in data["token"]:
                ret += E[{
                    "r": "red", "b": "blue", "w": "white"
                }.get(t, str(abs(data["rank"])))]

            ret += E["empty"] * (3 - len(data["token"]))
            ret += "".join([E[i] for i in data["item"]])
            l.append(u"<pre>%s</pre>" % ret)

        if notice:
            l.append(u"<b>%s</b>" % notice)

        return u"\n".join(l)

    def info_button(self, bot, update):
        query = update.callback_query
        username = query.from_user.username

        data = self.player_data.get(username)
        if not data:
            return {'text': '@%s: you are not in this game, please wait for the next game.' % username, 'show_alert': True}

        ret = []
        ret.append(u"Player %s" % username)

        rank = data["rank"]
        if rank > 0:
            player_faction = E["red"]
        elif rank < 0:
            player_faction = E["blue"]
        else:
            player_faction = E["white"]
        ret.append(u"Faction %s" % player_faction)

        ret.append(u"Available token %s" % "".join(self.token_convert(rank)))

        my_index = self.players.index(username)
        after_index = (my_index + 1) % len(self.players)
        player_after = self.players[after_index]
        after_faction = E[['red', 'blue'][(rank > 0) ^ (abs(rank) == 3)]]
        ret.append(u"Next player (%s) is %s" % (player_after, after_faction))

        # TODO: rank 3 can check player cards

        return {
            'text': u"\n".join(ret),
            'show_alert': True,
        }

    def token_convert(self, rank):
        red = {"c": E["red"], "s": E[str(abs(rank))], "w": E["white"]}
        blue = {"c": E["blue"], "s": E[str(abs(rank))], "w": E["white"]}
        raw_token = token_list[abs(rank)]
        if rank > 0:
            return map(lambda x: red[x], raw_token)
        elif rank < 0:
            return map(lambda x: blue[x], raw_token)
        else:
            return [E["black"], E["black"], E["0"]]

    def token_convert_single(self, rank, choice):
        red = {1: ("r", E["red"]), 2: ("r", E["red"]), 4: ("s", E[str(abs(rank))]), 3: ("w", E["white"])}
        blue = {1: ("b", E["blue"]), 2: ("b", E["blue"]), 4: ("s", E[str(abs(rank))]), 3: ("w", E["white"])}
        white = {1: ("r", E["red"]), 2: ("b", E["blue"]), 4: ("s", E[str(abs(rank))]), 3: ("w", E["white"])}
        if rank > 0:
            return red[choice]
        elif rank < 0:
            return blue[choice]
        else:
            return white[choice]


    def debug(self):
        from pprint import pprint
        pprint(self.player_data)


def help(bot, update):
    update.message.reply_text("Use /start to test this bot.")

def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)

instances = {}

def start_game(bot, update):
    cid = update.message.chat_id
    i = instances.get(cid)
    if i: i.cancel()
    instances[cid] = bb(bot, update, cid)

def main():
    updater = Updater("483679321:AAG9x30HL-o4UEIt5dn7tDgYTjsucx2YhWw")

    updater.dispatcher.add_handler(CommandHandler('start', help))
    updater.dispatcher.add_handler(CommandHandler('help', help))
    updater.dispatcher.add_handler(CallbackQueryHandler(router))
    updater.dispatcher.add_handler(CommandHandler('start_game', start_game))
    updater.dispatcher.add_error_handler(error)

    updater.start_polling(
        clean=True,
        timeout=5,
        read_latency=5,
    )

    updater.idle()


if __name__ == '__main__':
    main()
