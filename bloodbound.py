#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import uuid
from operator import neg
import random
from gamebot import GameManager, SingleChoice, MultipleChoice, StaticButtonManager, ParseMode

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
   "10": u"*️⃣",
   "attack": u"🗡",
   "give": u"↪️",
   "skill": u"💢",
   "interfere": u"⚠️",
   "noop": u"🔜 ",
   "reserved": u"🖌🗡🛡🔱🔰🔮💢♨️㊙️"
}

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

# Get faction name (Red/Blue/White) from rank
def faction_name(rank):
    if rank > 0: return 'red'
    if rank < 0: return 'blue'

def token_convert(rank):
    red = {"c": E["red"], "s": E[str(abs(rank))], "w": E["white"]}
    blue = {"c": E["blue"], "s": E[str(abs(rank))], "w": E["white"]}
    raw_token = token_list[abs(rank)]
    if rank > 0:
        return map(lambda x: red[x], raw_token)
    elif rank < 0:
        return map(lambda x: blue[x], raw_token)
    else:
        return [E["black"], E["black"], E["0"]]

def token_convert_single(rank, choice):
    red = {1: ("r", E["red"]), 2: ("r", E["red"]), 4: ("s", E[str(abs(rank))]), 3: ("w", E["white"])}
    blue = {1: ("b", E["blue"]), 2: ("b", E["blue"]), 4: ("s", E[str(abs(rank))]), 3: ("w", E["white"])}
    white = {1: ("r", E["red"]), 2: ("b", E["blue"]), 4: ("s", E[str(abs(rank))]), 3: ("w", E["white"])}
    if rank > 0:
        return red[choice]
    elif rank < 0:
        return blue[choice]
    else:
        return white[choice]

games = {}

def display_name(user):
    return user.user_name or user.full_name

class BloodBoundGame:

    def coroutine(self, bot, update):
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

        self.m = update.message.reply_text(
            self.log[0],
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

        id = uuid.uuid4()
        reply_markup=_make_choice_keyboard(id, ["Enter / Start"])

        while True:
            update = yield [CallbackQueryHandler(
                None, pattern=r"^" + id + r"#.-?[0-9]+$",
            )]
            player = update.effective_user
            if player in self.players:
                update.callback_query.answer("You are already in this game.")
                continue
            self.players.append(player)

            self.log.append(display_name(player) + " joined")

            if len(self.players) == 18: # Game will full after creator joins
                player = self.creator
                self.players.append(player)
                self.log.append(display_name(player) + " joined")

            if player == c['creator']:
                if len(self.players) <= 6:
                    update.callback_query.answer("Not enough players.")
                    continue

                c['log'].append("Game commencing.")
                self.m.edit_text(
                    text="\n".join(c['log']),
                    reply_markup=None,
                )
            else:
                self.m.edit_text(
                    text="\n".join(c['log']),
                    reply_markup=reply_markup,
                )

            update.callback_query.answer()

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
        assert len(res) == count
        return res

    def prepare_game(self):
        self.player_data = dict()
        ranks = self.shuffle_rank()
        for p, r in zip(self.players, ranks):
            self.player_data[p] = {"rank": r, "token": [], "token_available": token_list[abs(r)][:], "item": []}
        print(self.player_data)

        # Set target to blue 1 and red 1 respectively
        self.target = {'red': -1, 'blue': 1}

        self.static_buttons=[
            InlineKeyboardButton(E['info'], callback_data='info'),
        ]
        self.knife = self.players[random.randint(0, len(self.players) - 1)]

        self.round = 0
        
    def play_a_round(self):
        self.round += 1
        self.log = []


        self.m = self.m.reply_text(
            text=self.generate_game_message("%s action" % self.knife),
            parse_mode=ParseMode.HTML,
        )

        _, selection = yield from single_choice(
            original_message=self.m,
            candidate=[E['attack'], E['give']],
            whitelist=[self.knife],
            static_buttons=self.static_buttons,
        )
        is_give = (selection == 1)

        candidate = [display_name(x) for x in self.players if x != self.knife]
        _, victim = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[self.knife],
            static_buttons=self.static_buttons,
        )
        victim = candidate[victim]

        if is_give:
            old_knife, self.knife = self.knife, victim
            self.log.append("%s gave the knife to %s." % (old_knife, self.knife))
            self.display_game_message()
            return

        self.victim = victim
        self.log.append("%s is attacking %s" % (self.knife, self.victim))

        # Interfere

        interfere_candidate = []
        for player, data in self.player_data.iteritems():
            if player == self.knife or player == self.victim:
                continue
            if "s" in data["token_available"]:
                interfere_candidate.append(player)

        if len(interfere_candidate) > 0:
            yield from self.interfere(interfere_candidate)

        # Attack

        if len(self.player_data[self.victim]["token_available"]) == 0:
            self.game_end = True
            return 

        selected_token = yield from self.select_token()
                    
        token = token_convert_single(data["rank"], choice)
        self.log.append("%s selected %s token" % (self.victim, token[1]))
        self.display_game_message()
        data["token_available"].remove(choices[choice])
        data["token"].append(token[0])

        if selected_token = "s":
            yield from getattr(self, "skill" + data["rank"])()
        else:
            self.knife = self.victim
            self.debug()

    def select_token(self):
        if self.interfered:
            return "s"

        data = self.player_data[username]

        while True:
            _, selection = yield from single_choice(
                original_message=self.m,
                candidate=[E["red"], E["blue"], E["white"], E["skill"]],
                whitelist=[self.victim],
                static_buttons=self.static_buttons,
                text=self.generate_game_message(
                    "%s select token:" % display_name(self.victim)
                ),
            )

            # TODO validate token selection
            
            choices = ["x", "c", "c", "w", "s"]
            redo = False
            if choices[choice] not in data["token_available"]:
                redo = True
            if choices[choice] == "c":
                if (choice == 2 and data["rank"] > 0) or (choice == 1 and data["rank"] < 0):
                    redo = True
            if choices[choice] in ["c", "w"] and self.interfere_progress:
                redo = True


    def interfere(self, candidate):
        self.interfered = False

        guardians = []
        blacklist = []

        # stick to a same ID so consequential choices (made by other players) can also be accepted
        # repeated-choice will be blocked by blacklist
        id = uuid.uuid4()

        # TODO: set a timeout

        while len(candidate) != len(blacklist):
            update, selection = yield from single_choice(
                original_message=self.m,
                candidate=[E["interfere"], E["noop"]],
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
                ["interfere", "noop"][choice],
            ))

            self.display_game_message()

        # victim decide
        if len(ret) == 0:
            return 

        guardian_names = map(display_name, guardians)

        _, selection = yield from single_choice(
            original_message=self.m,
            candidate=guardian_names + [E["noop"]],
            whitelist=[self.victim],
            static_buttons=self.static_buttons,
            text=self.generate_game_message("%s accept interfere?" % self.victim),
        )

        if selection = len(guardians):
            self.log.append("%s rejected interference" % self.victim)
        else:
            self.log.append("%s accepted %s's interference" % (
                self.victim,
                
            ))
            self.victim = self.guardians[choice]
            self.interfered = True

        return

    def skill1(self):
        data = self.player_data[self.victim]
        rank = data["rank"]

        data['item'].append('feather')

        vf = faction_name(rank)
        sgn = 1 if rank > 0 else -1

        cur = 0
        for player, data in self.player_data.iteritems():
            if sgn * data["rank"] > cur:
                cur = data["rank"]
                curp = player

        self.target[vf] = curp

        return

        # Dummy yield to make function generator
        yield from range(0)

    def skill2(self):
        raise NotImplementedError

        # Dummy yield to make function generator
        yield from range(0)

    def skill3(self):
        candidate = [x for x in self.players if x != self.victim]
        self.m = MultipleChoice(
            self.bot, self.m, self.skill3_cb,
            candidate,
            self.victim,
            id=self.chat_id,
            static_btn_mgr=self.sbm,
            text=self.generate_game_message("%s select two players:" % self.knife),
        ).message

    def skill3_cb(self, bot, update, id, username, candidate, choices):
        if len(choices) != 2: 
            self.skill3()
        checked = [candidate[i] for i in choices[i]]
        data["checked"] += checked

        self.log.append("%s checked %s and %s's player card" % (
            self.victim, checked[0], checked[1],
        )
        self.display_game_message()

        self.round_end()

    def skill4(self):
        raise NotImplementedError

        # Dummy yield to make function generator
        yield from range(0)

    def skill5(self):
        raise NotImplementedError

        # Dummy yield to make function generator
        yield from range(0)

    def skill6(self):
        raise NotImplementedError

        # Dummy yield to make function generator
        yield from range(0)

    def skill7(self):
        raise NotImplementedError

        # Dummy yield to make function generator
        yield from range(0)

    def skill8(self):
        raise NotImplementedError

        # Dummy yield to make function generator
        yield from range(0)

    def skill9(self):
        raise NotImplementedError

        # Dummy yield to make function generator
        yield from range(0)

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

    if games.has_key(chat.id):
        update.message.reply_text("Another game is in progress.")
        return

    games[chat.id] = BloodBoundGame()

    yield from games[chat.id].coroutine(bot, update)

def cancel_game(bot, update):
    chat = update.effective_chat
    user = update.effective_user

    owner = games[chat.id].creator
    if user != owner:
        update.reply_text("You are not the owner of the game.")
        return

    update.cancel_current_conversation()

def info_button(bot, update):
    # Get `self` instance manually
    self = games[update.effective_chat.id]

    query = update.callback_query
    username = query.from_user.username

    data = self.player_data.get(username)
    if not data:
        return query.answer(
            '%s: you are not in this game, please wait for the next game.' % username,
            show_alert=True,
        )

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

    ret.append(u"Available token %s" % "".join(token_convert(rank)))

    my_index = self.players.index(username)
    after_index = (my_index + 1) % len(self.players)
    player_after = self.players[after_index]
    after_faction = E[['red', 'blue'][(rank > 0) ^ (abs(rank) == 3)]]
    ret.append(u"Next player (%s) is %s" % (player_after, after_faction))

    if data.has_key('checked'):
        ret.append(u"Checked players:")
        for player in data['checked']:
            r = self.player_data[player]["rank"]
            ret.append("%s%s%s" % (
                (player + "             ")[:8],
                faction_name(r),
                E[str(abs(r))],
            ))

    return query.answer(
        text=u"\n".join(ret),
        show_alert=True,
    )

def help(bot, update):
    update.message.reply_text("Use /start_game to test this bot.")

def main():
    svr = Updater("483679321:AAG9x30HL-o4UEIt5dn7tDgYTjsucx2YhWw")

    add = svr.dispatcher.add_handler
    add(InteractiveHandler(
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

    add(CommandHandler('help', help))

    svr.start_polling(
        clean=True,
        timeout=5,
    )
    svr.idle()

if __name__ == '__main__':
    main()
