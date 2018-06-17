#!/usr/bin/env python3.5
# -*- coding: utf-8 -*-

import logging
import uuid
import operator
import random

from telegram import InlineKeyboardButton, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

from interactivehandler import InteractiveHandler, ConversationCancelled
from gamebot import single_choice, _make_choice_keyboard
import gamebot

E={
   "empty": u"⚫️",
   'ok': u'⭕️',
   'tick': u'✔️',
   'info': u'ℹ️',
   "red": u"🔴",
   "blue": u"🔵",
   "white": u"⚪️",
   "any": u"㊙️",
   "1": u"1️⃣",
   "2": u"2️⃣",
   "3": u"3️⃣",
   "4": u"4️⃣",
   "5": u"5️⃣",
   "6": u"6️⃣",
   "7": u"7️⃣",
   "8": u"8️⃣",
   "9": u"9️⃣",
   "10": u"*️⃣",
   "attack": u"🗡",
   "give": u"↪️",
   "skill": u"#️⃣",
   "quill": u"quill", # Skill 1
   "shield0": u"🖤",   # Skill 6
   "shield1": u"💛",
   "shield2": u"💙",
   "shield3": u"💜",
   "sword0": u"🖤",
   "sword1": u"💛",
   "sword2": u"💙",
   "sword3": u"💜",
   "staff": u"staff", # Skill 8
   "fan": u"fan",     # Skill 9
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

# Get faction name (Red/Blue/White) from rank
def faction_name(rank):
    if abs(rank) == 10: return 'brown'
    if rank > 0: return 'red'
    if rank < 0: return 'blue'

def display_name(user):
    return user.username or user.full_name

class BloodBoundGame:
    games = {}

    def main(self, bot, update):
        self.bot = bot
        self.creator = update.effective_user

        self.players = []
        self.log = []

        yield from self.wait_for_players(update)

        self.prepare_game()

        while not self.game_end:
            yield from self.play_a_round()

        victim_rank = self.player_data[self.victim]["rank"]

        vf = faction_name( victim_rank)
        of = faction_name(-victim_rank)

        if victim_rank != self.target[of]: # Wrong target
            self.display_game_message("%s wins!" % E[vf])
        else:
            self.display_game_message("%s wins!" % E[of])


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
                update.callback_query.answer("You are already in this game.")
                continue

            if len(self.players) == 11 and player != self.creator:
                update.callback_query.answer("Game full.")
                continue

            if player == self.creator:
                #if len(self.players) < 5:
                if len(self.players) < 1:
                    update.callback_query.answer("Not enough players.")
                    continue

                if len(self.players) % 2 == 0:
                    update.callback_query.answer("Inquisitor is not implemented yet.")
                    continue

                self.players.append(player)
                self.log.append(display_name(player) + " joined")
                self.log.append("Game commencing.")
                self.m.edit_text(
                    text="\n".join(self.log),
                    reply_markup=None,
                )
                update.callback_query.answer()
                break
            else:
                self.players.append(player)
                self.log.append(display_name(player) + " joined")
                self.m.edit_text(
                    text="\n".join(self.log),
                    reply_markup=reply_markup,
                )
                update.callback_query.answer()

    def shuffle_rank(self):
        count = len(self.players)
        # no 3rd
        redteam = [1]
        blueteam = [1]
        brownteam = []
        x = list(range(2, 10))
        random.shuffle(x)
        if count % 2 == 1:
            brownteam.append(random.choice([-10, 10]))
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
        res = list(map(operator.neg, blueteam)) + redteam + brownteam
        random.shuffle(res)
        assert len(res) == count
        return res

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
        print(self.player_data)

        # Set target to blue 1 and red 1 respectively
        self.target = {'red': -1, 'blue': 1}


        self.static_buttons=[
            InlineKeyboardButton(E['info'], callback_data='info'),
        ]

        self.round = 0
        self.game_end = False

        # For skill 6
        self.shields = {}
        self.current_shield_id = 0

        self.knife = self.players[random.randint(0, len(self.players) - 1)]

    def get_action(self):
        self.m = self.m.reply_text(
            text=self.generate_game_message(
                "%s action" % display_name(self.knife)
            ),
            parse_mode=ParseMode.HTML,
        )

        _, selection = yield from single_choice(
            original_message=self.m,
            candidate=['Attack', 'Give'],
            whitelist=[self.knife],
            static_buttons=self.static_buttons,
        )
        import ipdb; ipdb.set_trace()
        is_give = (selection == 1)

        candidate = [display_name(x) for x in self.players if x != self.knife]
        _, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[self.knife],
            static_buttons=self.static_buttons,
        )
        victim = candidate[selection]

        return victim, is_give
        
    def play_a_round(self):
        self.round += 1
        self.log = []

        victim, is_give = yield from self.get_action()

        if is_give:
            old_knife, self.knife = self.knife, victim
            self.log.append("%s gave the knife to %s." % (old_knife, self.knife))
            self.display_game_message()
            return

        self.victim = victim
        self.log.append("%s is attacking %s" % (self.knife, self.victim))

        # Interfere (victim may be switched)
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

            icon = {
                'r': 'red', 'b': 'blue',
                'w': 'white', 's': str(abs(self.player_data[self.victim]['rank'])),
            }[selected_token[0]]

            self.log.append("%s selected %s token" % (
                display_name(self.victim),
                E[icon],
            ))

            # Skill
            if selected_token == "s":
                yield from getattr(self, "skill" + str(abs(self.player_data[self.victim]["rank"])))()

        self.knife = self.victim

        self.display_game_message()

        self.debug()

    def select_and_apply_token(self, instruction=None, forced=None):
        data = self.player_data[self.victim]

        if not data['token_available']:
            self.game_end = True
            return

        if forced:
            selected_token = forced
            assert selected_token in data['token_available']
        else:
            while True:
                update, selection = yield from single_choice(
                    original_message=self.m,
                    candidate=[E["red"], E["blue"], E["white"], E["skill"]],
                    whitelist=[self.victim],
                    static_buttons=self.static_buttons,
                    text=self.generate_game_message(
                        instruction or
                        "%s select token:" % display_name(self.victim)
                    ),
                )

                # validate token selection
                selected_token = ["r", "b", "w", "s"][selection]


                if selected_token in data['token_available']:
                    break

                # white faction
                if 'a' in data['token_available'] and selected_token != 's':
                    selected_token += 'a'
                    break

                # Skill 8
                if 'staff' in data['items'] and selected_token == 'w':
                    color = faction_name(data['rank'])[0]
                    if color in data['token_available']:
                        selected_token = 'w' + color
                    break

                update.callback_query.answer(
                    "Selection invalid, please retry.",
                    show_alert=True,
                )

        # convert skill token to display token
        if selected_token == 's':
            selected_token += str(abs(data['rank']))

        data['token_available'].remove(selected_token[-1])
        data['token_used'].append(selected_token)

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
                static_buttons=self.static_buttons,
            )

            blacklist.append(update.effective_user)

            if selection == 0: # interfere
                guardians.append(update.effective_user)

            self.log.append("%s chooses %s" % (
                display_name(update.effective_user),
                ["interfere", "pass"][selection],
            ))

            self.display_game_message()

        # victim decide
        if len(guardians) == 0:
            return 

        guardian_names = map(display_name, guardians)

        _, selection = yield from single_choice(
            original_message=self.m,
            candidate=guardian_names + [E["noop"]],
            whitelist=[self.victim],
            static_buttons=self.static_buttons,
            text=self.generate_game_message("%s accept interfere?" % self.victim),
        )

        if selection == len(guardians): # The (n+1)-th button
            self.log.append("%s rejected interference" % self.victim)
        else:
            self.log.append("%s accepted %s's interference" % (
                self.victim,
                guardians[selection]
            ))
            self.saved_victim, self.victim = self.victim, guardians[selection]
            return True

        return False

    def skill1(self):
        data = self.player_data[self.victim]
        rank = data['rank']

        data['item'].append('quill')

        vf = faction_name(rank)
        sgn = 1 if rank > 0 else -1

        cur = 0
        for player, data in self.player_data.items():
            if sgn * data["rank"] > cur:
                cur = data["rank"]
                curp = player

        self.target[vf] = curp

        return

        # Dummy yield to make function generator
        yield from range(0)

    def skill2(self):
        player = self.victim

        candidate = [x for x in self.players if x != player]

        _, selection = yield from gamebot.single_choice(
            original_message=self.m,
            candidate=map(display_name, candidate),
            whitelist=[player],
            text=self.generate_game_message(
                "%s a player to trigger skill:" % display_name(player),
            ),
            static_buttons=self.static_buttons,
        )
        self.victim = candidate[selection]
        self.log("%s casted skill on %s" % (
            display_name(player), display_name(self.victim),
        ))

        for i in ['1st', '2nd']:
            yield from self.select_and_apply_token(
                instruction="%s select %s token:" % (
                    display_name(self.victim), i
                )
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

            _, selection = yield from gamebot.single_choice(
                original_message=self.m,
                candidate=map(display_name, candidate),
                whitelist=[player],
                text=self.generate_game_message(
                    "%s select %s player to check:" % (display_name(player), i)
                ),
                static_buttons=self.static_buttons,
            )

            target = candidate[selection]
            pdata['checked'].append(target)
            self.log.append("%s checked %s" % (
                display_name(player), display_name(target),
            ))

    def skill4(self):
        if not self.saved_victim:
            return

        player = self.victim

        data = self.player_data[self.saved_victim]

        if not data['token_used']:
            selection = 0 # kill
        else:
            _, selection = yield from single_choice(
                original_message=self.m,
                candidate=['Kill', 'Heal'],
                whitelist=[player],
                text=self.generate_game_message(
                    "%s select kill or heal:" % display_name(player),
                ),
                static_buttons=self.static_buttons,
            )

        if selection == 0:
            self.log.append("%s killed %s" % (
                display_name(player),
                display_name(self.saved_victim),
            ))
            yield from self.select_and_apply_token()

        else:
            candidate = data['token_used']
            icons = [E[{
                'r': 'red', 'b': 'blue',
                'w': 'white', 's': str(abs(data['rank'])),
            }[i[0]]] for i in candidate]

            _, selection = yield from single_choice(
                original_message=self.m,
                candidate=icons,
                whitelist=[self.saved_victim],
                text=self.generate_game_message("%s select token for healing:" %
                    display_name(self.saved_victim)
                ),
                static_buttons=self.static_buttons,
            )

            selected_token = candidate[selection]
            self.log.append("%s healed %s" % (
                display_name(player),
                display_name(self.saved_victim),
            ))

            data['token_available'].append(selected_token[-1])
            data['token_used'].remove(selected_token)

    def skill5(self):
        player = self.victim

        candidate = [x for x in self.players if x != player]

        _, selection = yield from gamebot.single_choice(
            original_message=self.m,
            candidate=map(display_name, candidate),
            whitelist=[player],
            text=self.generate_game_message(
                "%s a player to trigger skill:" % display_name(player),
            ),
            static_buttons=self.static_buttons,
        )

        self.victim = candidate[selection]
        self.log.append("%s casted skill on %s" % (
            display_name(player), display_name(self.victim),
        ))

        yield from self.select_and_apply_token(
            forced='s' if 's' in self.player_data[self.victim]['token_available'] else None,
        )

    def skill6(self):
        player = self.victim

        candidate = [x for x in self.players if x != player]

        _, selection = yield from gamebot.single_choice(
            original_message=self.m,
            candidate=map(display_name, candidate),
            whitelist=[player],
            text=self.generate_game_message(
                "%s give a shield to a player:" % display_name(player),
            ),
            static_buttons=self.static_buttons,
        )

        target = candidate[selection]

        self.player_data[player]['item'].append('sword%d'  % self.current_shield_id)
        self.player_data[target]['item'].append('shield%d' % self.current_shield_id)

        self.log.append("%s gave a shield to %s" % (
            display_name(player), display_name(target),
        ))

        self.shields[self.current_shield_id] = {
            'sword': player,
            'shield': target,
        }
        self.current_shield_id += 1

    def skill6_invalidate(self):
        player = self.victim

        for n, i in list(self.shields.items()): # a read-only copy
            if i['sword'] == player:
                self.player_data[i['sword'] ].remove('sword%d'  % str(n))
                self.player_data[i['shield']].remove('shield%d' % str(n))
                self.log.append("%s's swords are invalidated" % display_name(player))
                del self.shields[i]

    def skill6_isprotected(self, player):
        for n, i in self.shields.items():
            if i['shield'] == player:
                self.log.append("%s is protected by the shield" % display_name(player))
                return True
        return False

    def skill7(self):
        player = self.victim
        target = self.knife

        self.log.append("%s casted skill on %s" % (
            display_name(player),
            display_name(target),
        ))

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

        _, selection = yield from gamebot.single_choice(
            original_message=self.m,
            candidate=map(display_name, candidate),
            whitelist=[player],
            text=self.generate_game_message(
                "%s give the staff to a player:" % display_name(player),
            ),
            static_buttons=self.static_buttons,
        )

        target = candidate[selection]
        self.player_data[target]['item'].append('staff')
        self.log.append("%s gave a staff to %s" % (
            display_name(player), display_name(target),
        ))


    def skill9(self):
        player = self.victim

        candidate = [x
            for x in self.players
            if x != player
            and 'fan' not in self.player_data[x]['item']
        ]

        _, selection = yield from gamebot.single_choice(
            original_message=self.m,
            candidate=map(display_name, candidate),
            whitelist=[player],
            text=self.generate_game_message(
                "%s give the fan to a player:" % display_name(player),
            ),
            static_buttons=self.static_buttons,
        )

        target = candidate[selection]
        self.player_data[target]['item'].append('fan')
        self.log.append("%s gave a fan to %s" % (
            display_name(player), display_name(target),
        ))

    def skill10(self):
        raise NotImplementedError

        # Dummy yield to make function generator
        yield from range(0)

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
            ret = "%-8s" % display_name(player)[:8]
            for t in data["token_used"]:
                icon = {
                    'r': 'red', 'b': 'blue',
                    'w': 'white', 's': str(abs(data['rank'])),
                }[t[0]]
                ret += E[icon]

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

def cancel_game(bot, update):
    chat = update.effective_chat
    user = update.effective_user

    owner = BloodBoundGame.games[chat.id].creator
    if user != owner:
        update.reply_text("You are not the owner of the game.")
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
            show_alert=True,
        )

    ret = []
    ret.append(u"Player %s" % display_name(user))
    ret.append(u"Faction: %s" % E[faction_name(data['rank'])])
    ret.append(u"Rank: %d(%s)" % (abs(data['rank']), rank_name[abs(data['rank'])]))

    token_icons = ""
    for t in data["token_available"]:
        icon = {
            'r': 'red', 'b': 'blue',
            'w': 'white', 'a': 'any',
            's': str(abs(data['rank'])),
        }[t]
        token_icons += E[icon]

    ret.append(u"Available token: %s" % token_icons)

    my_index = self.players.index(user)
    after_index = (my_index + 1) % len(self.players)
    player_after = self.players[after_index]
    rank = self.player_data[player_after]["rank"]
    after_faction = E[['blue', 'red'][(rank > 0) ^ (abs(rank) == 3)]]
    ret.append(u"Next player (%s) is %s" % (
        display_name(player_after), after_faction,
    ))

    if data['checked']:
        ret.append(u"Checked players:")
        for player in data['checked']:
            rank = self.player_data[player]["rank"]
            ret.append("%-8s%s%s" % (
                display_name(player)[:8],
                E[faction_name(rank)],
                E[str(abs(rank))],
            ))

    return query.answer(
        text=u"\n".join(ret),
        show_alert=True,
    )

def help(bot, update):
    update.message.reply_text("Use /start_game to test this bot.")

def main():
    svr = Updater("598818166:AAGkETNP_3hZ-cGLvrDnm_4iXVjGIgWKRvI")

    svr.dispatcher.add_handler(InteractiveHandler(
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

    svr.dispatcher.add_handler(CommandHandler('help', help))

    svr.start_polling(
        clean=True,
        timeout=300,
    )
    svr.idle()

if __name__ == '__main__':
    main()
