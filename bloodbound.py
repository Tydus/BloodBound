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

KNIFE = 1
INTERFERE = 2
INTERFERE_ACCEPT = 3
TOKEN = 4

END = 99

    
# Get faction name (Red/Blue/White) from rank
def faction_name(rank):
    if rank >  0: return 'red'
    if rank <  0: return 'blue'

# Get opposite faction
def opposite_faction(faction):
    return {'red': 'blue', 'blue': 'red'}[faction]

class BloodBoundGame:
    def __init__(self, bot, update, chat_id, gm):
        self.chat_id = chat_id
        self.bot = bot
        self.gm = gm
        self.creator = update.message.from_user.username
        self.log = ["Game starting"]
        self.m = update.message.reply_text(self.log[0], parse_mode=ParseMode.HTML,)
        self.players = []
        self.log = []
        self.sbm = StaticButtonManager()
        self.round = 0
        self.state = 0
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

        self.log.append("%s entered the game" % username)

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

        # Set target to blue 1 and red 1 respectively
        self.target = {'red': -1, 'blue': 1}

        self.sbm.add(E['info'], self.info_button)
        self.knife = self.players[random.randint(0, len(self.players) - 1)]
        self.round_start()
        
    def round_start(self):
        self.round += 1
        self.state = self.round * 100 + KNIFE
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
            self.log.append("%s gave the knife to %s." % (old_knife, self.knife))
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
        self.state = self.round * 100 + INTERFERE
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

        self.gm.schedule(interfere_timeout, 60, self.round)
        self.m = SingleChoice(
            self.bot, self.m, self.interfere_cb,
            [E["interfere"], E["noop"]],
            self.interfere_candidate, blacklist=self.blacklist,
            id=self.chat_id,
            static_btn_mgr=self.sbm,
            text=self.generate_game_message("%s: Guard %s? 60 secs to choose or don't guard." % (", ".join(self.interfere_candidate), self.victim)),
        ).message

    def interfere_timeout(self, round):
        if round * 100 + INTERFERE != self.state:
            return
        list(map(self.interfere_candidate.remove, set(self.players) - set(self.blacklist)))
        self.log.append("Others chose no-op")
        self.interfere_decide()


    def interfere_cb(self, bot, update, id, username, candidate, choice):
        self.blacklist.append(username)
        if choice == 2:
            self.interfere_candidate.remove(username)

        self.log.append("%s chooses %s" % (username, "interfere" if choice == 1 else "no-op"))

        self.display_game_message()

        print(self.players)
        print(self.blacklist)
        print(set(self.players) - set(self.blacklist))
        if set(self.players) - set(self.blacklist) == set():
            self.interfere_decide()
            return

        # fuck telegram throttle
        # self.m = SingleChoice(
        #     self.bot, self.m, self.interfere_cb,
        #     [E["interfere"], E["noop"]],
        #     self.interfere_candidate, blacklist=self.blacklist,
        #     id=self.chat_id,
        #     static_btn_mgr=self.sbm,
        #     text=self.generate_game_message("%s: Guard %s?" % (", ".join(set(self.players) - set(self.blacklist)), self.victim)),
        # ).message

    def interfere_decide(self):
        if len(self.interfere_candidate) == 0:
            return self.attack_result()
        else:
            self.state = self.round * 100 + INTERFERE_ACCEPT
            self.m = SingleChoice(
                self.bot, self.m, self.interfere_accept_cb,
                self.interfere_candidate + [E["noop"]],
                self.victim,
                id=self.chat_id,
                static_btn_mgr=self.sbm,
                text=self.generate_game_message("%s accept interfere?" % self.victim),
            ).message

    def interfere_accept_cb(self, bot, update, id, username, candidate, choice):
        if choice - 1 < len(self.interfere_candidate):
            self.log.append("%s accepted %s's interference" % (self.victim, self.interfere_candidate[choice - 1]))
            self.victim = self.interfere_candidate[choice - 1]
        self.interfere_progress = True
        self.attack_result()

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

        self.round_end()

    def skill2(self):
        self.round_end()

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
        self.round_end()

    def skill5(self):
        self.round_end()

    def skill6(self):
        self.round_end()

    def skill7(self):
        self.round_end()

    def skill8(self):
        self.round_end()

    def skill9(self):
        self.round_end()

    def skill10(self):
        self.round_end()

    def attack_result(self):
        self.state = self.round * 100 + TOKEN
        if len(self.player_data[self.victim]["token_available"]) == 0:
            return self.game_end()

        self.m = SingleChoice(
            self.bot, self.m, self.attack_result_cb,
            [E["red"], E["blue"], E["white"], E["skill"]],
            self.victim,
            id=self.chat_id,
            static_btn_mgr=self.sbm,
            text=self.generate_game_message("%s select token:" % self.victim),
        ).message

    def game_end(self):
        self.state = self.round * 100 + END
        victim_rank = self.player_data[self.victim]["rank"]

        vf = faction_name(victim_rank)
        of = opposite_faction(vf)

        if victim_rank != self.target[of]: # Wrong target
            return self.game_result(E[vf])

        return self.game_result(E[of])

        #if abs(self.player_data[self.victim]["rank"]) == 1:
        #    if self.player_data[self.victim]["rank"] > 0:
        #        return self.game_result(E["blue"])
        #    else:
        #        return self.game_result(E["red"])
        #else:
        #    if self.player_data[self.victim]["rank"] > 0:
        #        return self.game_result(E["red"])
        #    else:
        #        return self.game_result(E["blue"])

    def attack_result_cb(self, bot, update, id, username, candidate, choice):
        assert username == self.victim

        data = self.player_data[username]

        choices = ["x", "c", "c", "w", "s"]
        redo = False
        if choices[choice] not in data["token_available"]:
            redo = True
        if choices[choice] == "c":
            if (choice == 2 and data["rank"] > 0) or (choice == 1 and data["rank"] < 0):
                redo = True
        if choices[choice] in ["c", "w"] and self.interfere_progress:
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
            return
            
        token = self.token_convert_single(data["rank"], choice)
        self.log.append("%s selected %s token" % (self.victim, token[1]))
        self.display_game_message()
        data["token_available"].remove(choices[choice])
        data["token"].append(token[0])

        if choices[choice] == "s": # Trigger skill
            getattr(self, "skill" + data["rank"])()
        else:
            self.round_end()

    def round_end(self):
        self.knife = self.victim
        self.debug()
        self.interfere_progress = False
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
            return {'text': '%s: you are not in this game, please wait for the next game.' % username, 'show_alert': True}

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

        if data.has_key('checked'):
            ret.append(u"Checked players:")
            for player in data['checked']:
                r = self.player_data[player]["rank"]
                ret.append("%s%s%s" % (
                    (player + "             ")[:8],
                    faction_name(r),
                    E[str(abs(r))],
                ))

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

    def cancel(self):
        if self.round:
            self.display_game_message("Game cancelled.")
        else:
            self.m.edit_text(
                text="<b>Game cancelled.</b>",
                parse_mode=ParseMode.HTML,
            )

def help(bot, update):
    update.message.reply_text("Use /start_game to test this bot.")

def main():
    gm = GameManager("483679321:AAG9x30HL-o4UEIt5dn7tDgYTjsucx2YhWw", BloodBoundGame)

    gm.add_command_handler('help', help)

    gm.start(
        clean=True,
        timeout=5,
        read_latency=5,
    )

if __name__ == '__main__':
    main()
