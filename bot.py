#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import uuid
import operator
import random
import os
import sys

import telegram
# Hook User's repr and str to display cleanly
def display_name(user):
    return user.username or user.full_name
telegram.User.__repr__ = display_name
telegram.User.__str__  = display_name

# Hook CallbackQuery's answer() to handle(ignore) timeout
telegram.CallbackQuery._real_answer = telegram.CallbackQuery.answer
def __answer(self, *args, **kwargs):
    try:
        return self._real_answer(*args, **kwargs)
    except telegram.error.BadRequest as e:
        print("callback_query.answer(): %s")
telegram.CallbackQuery.answer = __answer

from telegram import InlineKeyboardButton, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

from interactivehandler import InteractiveHandler, ConversationCancelled
from gamebot import single_choice, _make_choice_keyboard

E={
   "empty": u"⚫️",
   'ok': u'⭕️',
   'tick': u'✔️',
   'info': u'ℹ️',
   "r": u"🔴",
   "b": u"🔵",
   "w": u"⚪️",
   "a": u"㊙️",
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
   "attack": u"🗡",
   "give": u"↪️",
   "s": u"#️⃣",
   "quill": u"quill",      # Skill 1
   "shield0": u"🖤",        # Skill 6
   "shield1": u"💛",
   "shield2": u"💙",
   "shield3": u"💜",
   "sword0": u"🖤",
   "sword1": u"💛",
   "sword2": u"💙",
   "sword3": u"💜",
   "staff": u"staff",      # Skill 8
   "fan": u"fan",          # Skill 9
   "real_curse": u"curse", # Skill 10
   "fake_curse": u"curse", # Skill 10
   "reserved": u"🖌🗡🛡🔱🔰🔮💢♨️㊙️"
}

rank_name = [
    None,
    "Elder",
    "Assassin",
    "Harlequin",
    "Alchemist",
    "Mentalist",
    "Guardian",
    "Berserker",
    "Mage",
    "Courtesan",
    "Inquisitor",
]

token_list = [
    None,
    ["c", "c", "s"],
    ["w", "w", "s"],
    ["w", "w", "s"],
    ["w", "w", "s"],
    ["c", "c", "s"],
    ["c", "c", "s"],
    ["c", "w", "s"],
    ["c", "w", "s"],
    ["c", "w", "s"],
    ["a", "a", "s"],
]

# About Token colors:
# x or xy
# x: display token color
# y: real token color (if not eq display color)
# e.g.: 1 with a 'staff' can select a 'wr' token,
# which means a red token displayed in white.
#
# y is decided while the token is spelt out,
# and should be removed while drawing back.

# Get user's REAL faction name (Red/Blue/White) from rank
def faction_name(rank):
    if abs(rank) == 10: return 'white'
    if rank > 0: return 'red'
    if rank < 0: return 'blue'

class BloodBoundGame:
    games = {}

    def main(self, bot, update):
        self.bot = bot
        self.creator = update.effective_user

        self.players = []
        self.log = []

        self.round = 0

        yield from self.wait_for_players(update)

        self.prepare_game()

        while not self.game_end:
            yield from self.play_a_round()

        self.show_winner()

    def show_winner(self):
        victim_rank = self.player_data[self.victim]["rank"]

        if abs(victim_rank) == 10:
            self.display_game_message("Inquisitor wins!")
            return

        vf = faction_name( victim_rank)
        of = faction_name(-victim_rank)

        if victim_rank != self.target[of]: # Wrong target
            winner = vf
        else:
            winner = of

        for player, data in self.player_data.items():
            if (data['rank'] == self.target[winner] and
               "real_curse" in data['item']
            ):
                self.display_game_message("Inquisitor wins!")
                return

        self.display_game_message("%s wins!" % winner)

    def wait_for_players(self, update):
        self.log = ["Looking for players"]

        id = uuid.uuid4()
        reply_markup=_make_choice_keyboard(id, ["Enter / Start"])
        self.m = update.message.reply_text(
            self.log[0],
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

        while True:
            update = yield [CallbackQueryHandler(
                None, pattern=r"^" + str(id) + r"#-?[0-9]+$",
            )]
            player = update.effective_user
            if player in self.players:
                update.callback_query.answer(
                    "You are already in this game.", True,
                )
                continue

            if len(self.players) == 11 and player != self.creator:
                update.callback_query.answer("Game full.", True)
                continue

            if player == self.creator:
                if len(self.players) < 5:
                    update.callback_query.answer("Not enough players.", True)
                    continue

                self.players.append(player)
                self.log.append("%s joined" % player)
                self.log.append("Game commencing.")
                self.m.edit_text(
                    text="\n".join(self.log),
                    reply_markup=None,
                )
                update.callback_query.answer()
                break
            else:
                self.players.append(player)
                self.log.append("%s joined" % player)
                self.m.edit_text(
                    text="\n".join(self.log),
                    reply_markup=reply_markup,
                )
                update.callback_query.answer()

    def shuffle_rank(self):
        ret = []

        count = len(self.players)
        cards = list(range(1, 10))

        if count % 2 == 1:
            ret.append(random.choice([-10, 10]))
            count -= 1
        
        count //= 2

        random.shuffle(cards)
        ret += cards[:count]

        random.shuffle(cards)
        ret += list(map(operator.neg, cards[:count]))

        random.shuffle(ret)

        assert len(ret) == len(self.players)
        return ret

    def prepare_game(self):
        self.player_data = dict()
        ranks = self.shuffle_rank()

        for p, r in zip(self.players, ranks):
            # convert 'c' to the real color (r / b)
            t = token_list[abs(r)]
            t = list("".join(t).replace('c', faction_name(r)[0]))

            self.player_data[p] = {
                "rank": r,
                "token_used": [],
                "token_available": t,
                "item": [],
                "checked": [],
            }
        self.debug()

        self.target = {
            'red':  max(i for i in ranks if i < 0),
            'blue': min(i for i in ranks if i > 0),
        }

        self.static_buttons=[
            InlineKeyboardButton(E['info'], callback_data='info'),
        ]

        self.game_end = False

        # Skill 6
        self.shields = {}
        self.current_shield_id = 0

        # Skill 10
        if len(self.players) % 2 == 1:
            self.available_curse = (
                ["real_curse"] +
                ["fake_curse"] * ((len(self.players) - 5) // 2)
            )
        else:
            self.available_curse = None

        self.knife = self.players[random.randint(0, len(self.players) - 1)]

    def get_action(self):
        self.m = self.m.reply_text(
            text=self.generate_game_message("%s action" % self.knife),
            parse_mode=ParseMode.HTML,
        )

        data = self.player_data[self.knife]

        if abs(data['rank']) == 10 and data['token_available'] == []:
            # Skill 10
            self.log.append("Inquisitor %s cannot attack" % self.knife)
            is_give = 1
        else:
            _, selection = yield from single_choice(
                original_message=self.m,
                candidate=['Attack', 'Pass'],
                whitelist=[self.knife],
                text=self.generate_game_message("%s select action" % self.knife),
                static_buttons=self.static_buttons,
            )
            is_give = (selection == 1)

        candidate = [x for x in self.players if x != self.knife]
        _, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[self.knife],
            text=self.generate_game_message("%s select target" % self.knife),
            static_buttons=self.static_buttons,
        )
        target = candidate[selection]

        return target, is_give
        
    def play_a_round(self):
        self.round += 1
        self.log = []

        target, is_give = yield from self.get_action()

        if is_give:
            self.log.append("%s gave the knife to %s." % (self.knife, target))
            self.knife = target
            self.display_game_message()
            return

        self.victim = target
        self.log.append("%s is attacking %s" % (self.knife, self.victim))

        # Interfere (victim may be switched)
        interfered = False

        # Skill 9
        if "fan" not in self.player_data[self.victim]['item']:
            interfered = yield from self.interfere()

        # Attack

        # Skill 6
        if not interfered and self.skill6_isprotected(self.victim):
            pass

        else:
            selected_token = yield from self.select_and_apply_token(
                forced='s' if interfered else None,
            )

            # Game end
            if self.game_end: return

            self.log.append("%s selected %s token" % (
                self.victim, E[selected_token[0]],
            ))

            # Skill
            if selected_token[-1] == "s":
                func = getattr(self, "skill" + str(abs(self.player_data[self.victim]["rank"])))
                yield from func()

        self.knife = self.victim

        self.display_game_message()

        self.debug()

    def select_and_apply_token(self, instruction=None, forced=None):
        data = self.player_data[self.victim]

        if not data['token_available']:
            self.game_end = True
            return None

        if forced:
            selected_token = forced
            assert selected_token in data['token_available']
        else:
            while True:
                candidate = ['r', 'b', 'w', 's']

                update, selection = yield from single_choice(
                    original_message=self.m,
                    candidate=list(map(E.get, candidate)),
                    whitelist=[self.victim],
                    static_buttons=self.static_buttons,
                    text=self.generate_game_message(
                        instruction or "%s select token:" % self.victim
                    ),
                )

                # validate token selection
                selected_token = candidate[selection]


                if selected_token in data['token_available']:
                    break

                # white faction
                if 'a' in data['token_available'] and selected_token != 's':
                    selected_token += 'a'
                    break

                # Skill 8
                if 'staff' in data['item'] and selected_token == 'w':
                    color = faction_name(data['rank'])[0]
                    if color in data['token_available']:
                        selected_token = 'w' + color
                    break

                update.callback_query.answer(
                    "Selection invalid, please retry.", True
                )

        # convert skill token to display token
        if selected_token == 's':
            selected_token = "%ds" % abs(data['rank']) % 10

        data['token_available'].remove(selected_token[-1])
        data['token_used'].append(selected_token)

        # Skill 6
        if data['token_available'] == [] and abs(data['rank']) == 6:
            self.skill6_invalidate()

        return selected_token

    def interfere(self):
        self.saved_victim = None

        candidate = []
        for player, data in self.player_data.items():
            if player == self.knife or player == self.victim:
                continue
            if "s" in data["token_available"]:
                candidate.append(player)

        if len(candidate) == 0:
            return

        guardians = []
        blacklist = []

        # stick to a same ID so consequential choices (made by other players) can also be accepted
        # repeated-choice will be blocked by blacklist
        id = uuid.uuid4()

        # TODO: set a timeout

        while len(candidate) != len(blacklist):
            update, selection = yield from single_choice(
                original_message=self.m,
                candidate=["interfere", "pass"],
                whitelist=candidate,
                blacklist=blacklist,
                id=id,
                text=self.generate_game_message(
                    "everyone else select interfere or pass"
                ),
                static_buttons=self.static_buttons,
            )

            blacklist.append(update.effective_user)

            if selection == 0: # interfere
                guardians.append(update.effective_user)

            self.log.append("%s chooses %s" % (
                update.effective_user,
                ["interfere", "pass"][selection],
            ))

            self.display_game_message()

        # victim decide
        if len(guardians) == 0:
            return 

        _, selection = yield from single_choice(
            original_message=self.m,
            candidate=guardians + ["None"],
            whitelist=[self.victim],
            static_buttons=self.static_buttons,
            text=self.generate_game_message("%s accept interfere?" % self.victim),
        )

        if selection == len(guardians): # The (n+1)-th button
            self.log.append("%s rejected interference" % self.victim)
        else:
            self.log.append("%s accepted %s's interference" % (
                self.victim, guardians[selection]
            ))
            self.saved_victim, self.victim = self.victim, guardians[selection]
            return True

        return False

    def skill1(self):
        data = self.player_data[self.victim]

        data['item'].append('quill')

        vf = faction_name(data['rank']) # will not be white

        ranks = [
            i['rank']
            for i in self.player_data.values()
            if abs(i['rank']) != 10
        ]

        if data['rank'] > 0:
            self.target[vf] = max(ranks)
        else:
            self.target[vf] = min(ranks)

        return

        # Dummy yield to make function generator
        yield from range(0)

    def skill2(self):
        player = self.victim

        candidate = [x for x in self.players if x != player]

        _, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[player],
            text=self.generate_game_message(
                "%s a player to trigger skill:" % player,
            ),
            static_buttons=self.static_buttons,
        )
        self.victim = candidate[selection]
        self.log.append("%s casted skill on %s" % (player, self.victim))

        for i in ['1st', '2nd']:
            yield from self.select_and_apply_token(
                instruction="%s select %s token:" % (self.victim, i),
            )

    def skill3(self):
        player = self.victim
        pdata = self.player_data[player]

        for i in ['1st', '2nd']:
            candidate = [x
                for x in self.players
                if x != player
                and x not in pdata['checked']
            ]

            if not candidate:
                self.log.append("No enough player to be checked.")
                break

            _, selection = yield from single_choice(
                original_message=self.m,
                candidate=candidate,
                whitelist=[player],
                text=self.generate_game_message(
                    "%s select %s player to check:" % (player, i),
                ),
                static_buttons=self.static_buttons,
            )

            target = candidate[selection]
            pdata['checked'].append(target)
            self.log.append("%s checked %s" % (player, target))

    def skill4(self):
        if not self.saved_victim:
            return

        player = self.victim

        data = self.player_data[self.saved_victim]

        if not data['token_used']:
            selection = 0 # kill
            self.log.append("%s has no token shown, %s must kill %s" %(
                self.saved_victim, self.victim, self.saved_victim,
            ))
        else:
            _, selection = yield from single_choice(
                original_message=self.m,
                candidate=['kill', 'heal'],
                whitelist=[player],
                text=self.generate_game_message(
                    "%s select kill or heal:" % player,
                ),
                static_buttons=self.static_buttons,
            )

        if selection == 0:
            # Temporarily switch victim 
            self.victim = self.saved_victim
            self.log.append("%s killed %s" % (player, self.saved_victim))
            yield from self.select_and_apply_token()
            self.victim = player

        else:
            candidate = data['token_used']
            if len(candidate) == 1:
                selected_token = candidate[0]
            else:
                _, selection = yield from single_choice(
                    original_message=self.m,
                    candidate=[E[i[0]] for i in candidate],
                    whitelist=[self.saved_victim],
                    text=self.generate_game_message(
                        "%s select token for healing:" % self.saved_victim
                    ),
                    static_buttons=self.static_buttons,
                )

                selected_token = candidate[selection]

            self.log.append("%s healed %s" % (player, self.saved_victim))

            data['token_available'].append(selected_token[-1])
            data['token_used'].remove(selected_token)

    def skill5(self):
        player = self.victim

        candidate = [x for x in self.players if x != player]

        _, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[player],
            text=self.generate_game_message(
                "%s a player to trigger skill:" % player,
            ),
            static_buttons=self.static_buttons,
        )

        self.victim = candidate[selection]
        self.log.append("%s casted skill on %s" % (player, self.victim))

        yield from self.select_and_apply_token(
            forced='s' if 's' in self.player_data[self.victim]['token_available'] else None,
        )

    def skill6(self):
        player = self.victim

        candidate = [x for x in self.players if x != player]

        _, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[player],
            text=self.generate_game_message(
                "%s give a shield to a player:" % player,
            ),
            static_buttons=self.static_buttons,
        )

        target = candidate[selection]

        self.player_data[player]['item'].append('sword%d'  % self.current_shield_id)
        self.player_data[target]['item'].append('shield%d' % self.current_shield_id)

        self.log.append("%s gave a shield to %s" % (player, target))

        self.shields[self.current_shield_id] = {
            'sword': player,
            'shield': target,
        }
        self.current_shield_id += 1

    def skill6_invalidate(self):
        player = self.victim

        has_sword = False
        for k, v in list(self.shields.items()): # a read-only copy
            if v['sword'] == player:
                self.player_data[v['sword'] ]['item'].remove('sword%d'  % k)
                self.player_data[v['shield']]['item'].remove('shield%d' % k)
                has_sword = True
                del self.shields[k]

        if has_sword:
            self.log.append("%s's swords are invalidated" % player)

    def skill6_isprotected(self, player):
        for n, i in self.shields.items():
            if i['shield'] == player:
                self.log.append("%s is protected by the shield" % player)
                return True
        return False

    def skill7(self):
        player = self.victim
        target = self.knife

        self.log.append("%s casted skill on %s" % (player, target))

        # Temporarily switch victim for select_and_apply_token()
        self.victim = target
        yield from self.select_and_apply_token()
        self.victim = player

    def skill8(self):
        player = self.victim
        pdata = self.player_data[player]

        if 'staff' not in pdata['item']:
            pdata['item'].append('staff')

        candidate = [x
            for x in self.players
            if x != player
            and 'staff' not in self.player_data[x]['item']
        ]

        _, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[player],
            text=self.generate_game_message(
                "%s give the staff to a player:" % player,
            ),
            static_buttons=self.static_buttons,
        )

        target = candidate[selection]
        self.player_data[target]['item'].append('staff')
        self.log.append("%s gave a staff to %s" % (player, target))

    def skill9(self):
        player = self.victim

        candidate = [x
            for x in self.players
            if x != player
            and 'fan' not in self.player_data[x]['item']
        ]

        _, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[player],
            text=self.generate_game_message(
                "%s give the fan to a player:" % player,
            ),
            static_buttons=self.static_buttons,
        )

        target = candidate[selection]
        self.player_data[target]['item'].append('fan')
        self.log.append("%s gave a fan to %s" % (player, target))

    def skill10(self):
        player = self.victim

        if self.available_curse == []:
            self.log.append("%s have no curses left" % player)
            return

        candidate = [x
            for x in self.players
            if x != player
            #and 'real_curse' not in self.player_data[x]['item']
            #and 'fake_curse' not in self.player_data[x]['item']
        ]

        _, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[player],
            text=self.generate_game_message(
                "%s give the curse to a player:" % player,
            ),
            static_buttons=self.static_buttons,
        )
        target = candidate[selection]

        random.shuffle(self.available_curse)

        _, selection = yield from single_choice(
            original_message=self.m,
            candidate=list(map(E.get, self.available_curse)),
            whitelist=[target],
            text=self.generate_game_message("%s select a curse:" % target),
            static_buttons=self.static_buttons,
        )

        curse = self.available_curse[selection]
        self.player_data[target]['item'].append(curse)
        self.available_curse.remove(curse)

        self.log.append("%s gave a curse to %s" % (player, target))

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

        for player, data in self.player_data.items():
            ret = "%-8s" % str(player)[:8]
            for t in data["token_used"]:
                ret += E[t[0]]

            ret += E["empty"] * (3 - len(data["token_used"]))
            ret += "".join([E[i] for i in data["item"]])
            l.append(u"<pre>%s</pre>" % ret)

        if notice:
            l.append("")
            l.append(u"<b>%s</b>" % notice)

        return u"\n".join(l)

    def debug(self):
        from pprint import pprint
        pprint(self.player_data)

    def cancel(self):
        if self.round:
            self.display_game_message("Game cancelled.")
        else:
            self.m.edit_text(
                text="<b>Game cancelled.</b>",
                parse_mode=ParseMode.HTML,
            )

def start_game(bot, update):
    chat = update.effective_chat

    if chat.type not in ['group', 'supergroup']:
        update.message.reply_text("The game must be started in a group.")
        return

    if chat.id in BloodBoundGame.games:
        update.message.reply_text("Another game is in progress.")
        return

    self = BloodBoundGame()
    BloodBoundGame.games[chat.id] = self

    try:
        yield from self.main(bot, update)
    except ConversationCancelled as e:
        self.cancel()
    finally:
        del BloodBoundGame.games[chat.id]

def cancel_game(bot, update):
    chat = update.effective_chat
    user = update.effective_user

    owner = BloodBoundGame.games[chat.id].creator
    if user != owner:
        update.message.reply_text("You are not the owner of the game.")
        return

    update.cancel_current_conversation()

def info_button(bot, update):
    # Get `self` instance manually
    self = BloodBoundGame.games[update.effective_chat.id]

    query = update.callback_query
    user = query.from_user

    data = self.player_data.get(user)
    if not data:
        return query.answer(
            'You are not in this game, please wait for the next game.',
            True,
        )

    ret = []
    ret.append(u"Player %s" % display_name(user))
    ret.append(u"Faction: %s" % E[faction_name(data['rank'])[0]])
    ret.append(u"Rank: %d(%s)" % (abs(data['rank']), rank_name[abs(data['rank'])]))

    icons = ""
    for t in data['token_available']:
        if t == 's':
            icons += E[str(abs(data['rank']) % 10)]
        else:
            icons += E[t]

    ret.append(u"Available token: %s" % icons)

    my_index = self.players.index(user)
    after_index = (my_index + 1) % len(self.players)
    player_after = self.players[after_index]
    rank = self.player_data[player_after]["rank"]
    after_faction = E[['b', 'r'][(rank > 0) ^ (abs(rank) == 3)]]
    ret.append(u"Next player (%s) is %s" % (
        display_name(player_after), after_faction,
    ))

    if data['checked']:
        ret.append(u"Checked players:")
        for player in data['checked']:
            rank = self.player_data[player]["rank"]
            ret.append("%s: %s%s" % (
                player,
                E[faction_name(rank)[0]],
                E[str(abs(rank))],
            ))

    return query.answer(u"\n".join(ret), True)

def help(bot, update):
    update.message.reply_text("Use /start_game to test this bot.")

def main():
    updater = Updater(os.environ['BOT_TOKEN'])

    updater.dispatcher.add_handler(InteractiveHandler(
        start_game,
        entry_points = [
            CommandHandler('start_game', None),
        ],
        fallbacks = [
            CommandHandler('cancel', cancel_game),
            CallbackQueryHandler(info_button, pattern=r"^info$"),
        ],
        per_chat=True,
        per_user=False,
        per_message=False,
    ))

    updater.dispatcher.add_handler(CommandHandler('help', help))

    webhook_port = os.environ.get('WEBHOOK_PORT')
    if webhook_port:
        sys.stdout.flush()

        webhook_url=os.environ.get('URL_PREFIX', 'https://%s:%s/' % (
            os.environ['WEBHOOK_FQDN'], webhook_port,
        )) + "api/" + os.environ['BOT_TOKEN']

        updater.start_webhook(
            listen=os.environ.get('WEBHOOK_LISTEN', '0.0.0.0'),
            port=int(webhook_port),
            url_path='api/' + os.environ['BOT_TOKEN'],
            key=os.environ.get('WEBHOOK_KEY'),
            cert=os.environ.get('WEBHOOK_CERT'),
            webhook_url=webhook_url,
            clean=True,
        )

        info = updater.bot.get_webhook_info()
        print("Webhook info:")
        import pprint; pprint.pprint(str(info))

    else:
        updater.start_polling(clean=True, timeout=10)

    print("Blood Bound Bot ready for serving!")
    sys.stdout.flush()

    updater.idle()

if __name__ == '__main__':
    main()
