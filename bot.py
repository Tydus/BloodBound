#!/usr/bin/env python3

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

# For pygettext
_T = lambda s: s

E={
    "empty": u"⚫️",
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
    "s": u"#️⃣",
    "quill": u"✒️",      # Skill 1
    "shieldg": u"🛡",    # Skill 6
    "swordg": u"🗡",
    "shieldp": u"🔰",
    "swordp": u"🔪",
    "staff": u"⚕",      # Skill 8
    "fan": u"fan",       # Skill 9
    "curse0": u"📕",     # Skill 10
    "curse1": u"📗",
    "curse2": u"📘",
    "curse3": u"📙",
    "reserved": u"🔮♨️",
}

rank_name = [
    None,
    _T("Elder"),
    _T("Assassin"),
    _T("Harlequin"),
    _T("Alchemist"),
    _T("Mentalist"),
    _T("Guardian"),
    _T("Berserker"),
    _T("Mage"),
    _T("Courtesan"),
    _T("Inquisitor"),
]

quick_help = [
    None,
    _T("Take a ✒️"),
    _T("Give a player 2 damages and pass him the knife"),
    _T("Inspect two character cards secretly"),
    _T("Force the interceptor to be damaged/healed once (only available when intercepted)"),
    _T("Give a player 1 damage (must be the number if possible) and pass him the knife"),
    _T("Give a 🛡/🔰 to a player and take 🗡/🔪"),
    _T("Give a damage to the player attacked you"),
    _T("Take a ⚕️ and give a ⚕️ to another player"),
    _T("Give a (Fan) to another player"),
    _T("Give a 📕📗📘📙 to a player"),
]

token_list = [
    None,
    ['c', 'c', 's'],
    ['w', 'w', 's'],
    ['w', 'w', 's'],
    ['w', 'w', 's'],
    ['c', 'c', 's'],
    ['c', 'c', 's'],
    ['c', 'w', 's'],
    ['c', 'w', 's'],
    ['c', 'w', 's'],
    ['a', 'a', 's'],
]

# About Token colors:
# x or xy
# x: display token color
# y: real token color (if not eq display color)
# e.g.: inquisitor can select a 'wa' token,
# which means a 'any' token displayed in white.
#
# y is decided while the token is spelt out,
# and should be removed while drawing back.

# Get user's REAL faction name (Red/Blue/White) from rank
def faction_name(rank):
    if abs(rank) == 10: return _T("white")
    if rank > 0: return _T("red")
    if rank < 0: return _T("blue")

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
        victim_rank = self.player_data[self.victim]['rank']

        # Skill 10
        if abs(victim_rank) == 10:
            self.display_game_message(_("Inquisitor wins!"))
            return

        vf = faction_name( victim_rank)
        of = faction_name(-victim_rank)

        if victim_rank != self.target[of]: # Wrong target
            winner = vf
        else:
            winner = of

        # Skill 10
        if self.real_curse != None:
            real_curse_book = 'curse%d' % self.real_curse
            self.log.append(_("The real curse book is %s.") % E[real_curse_book])

            for player, data in self.player_data.items():
                if (data['rank'] == self.target[winner] and
                    real_curse_book in data['item']
                ):
                    self.display_game_message(_("Inquisitor wins!"))
                    return

        self.display_game_message(_("%s wins!") % _(winner))

    def wait_for_players(self, original_update):
        # Workaround: don't use 'update' here to avoid pollution to
        # the argument. '_' is worked by checking argument's name.
        self.log = [_("Looking for players")]

        id = uuid.uuid4()
        reply_markup=_make_choice_keyboard(id, [_("Enter / Start")])
        self.m = original_update.message.reply_text(
            self.log[0],
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

        while True:
            update = yield [CallbackQueryHandler(
                None, pattern=r'^' + str(id) + r'#-?[0-9]+$',
            )]
            player = update.effective_user
            if player in self.players:
                update.callback_query.answer(
                    _("You are already in this game."), True,
                )
                continue

            if len(self.players) == 11 and player != self.creator:
                update.callback_query.answer(_("Game full."), True)
                continue

            if player == self.creator:
                if len(self.players) < 1:
                    update.callback_query.answer(
                        _("Not enough players."), True,
                    )
                    continue

                self.players.append(player)
                self.log.append(_("%s joined") % player)
                self.log.append(_("Game commencing."))
                self.m.edit_text(
                    text='\n'.join(self.log),
                    reply_markup=None,
                )
                update.callback_query.answer()
                break
            else:
                self.players.append(player)
                self.log.append(_("%s joined") % player)
                self.m.edit_text(
                    text='\n'.join(self.log),
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
            t = list(''.join(t).replace('c', faction_name(r)[0]))

            self.player_data[p] = {
                'rank': r,
                'token_used': [],
                'token_available': t,
                'item': [],
                'checked': [],
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
        shield_colors = ['green', 'purple']
        random.shuffle(shield_colors)
        self.available_shields = {6: shield_colors[0], -6: shield_colors[1]}
        self.shields = []

        # Skill 10
        if len(self.players) % 2 == 1:
            self.available_curse = ["curse%d" % i for i in range(4)]

            size = max(2, (len(self.players) - 3) // 2)
            self.available_curse = self.available_curse[:size]
            self.real_curse = random.randint(0, size - 1)
        else:
            self.real_curse = None

        self.knife = self.players[random.randint(0, len(self.players) - 1)]

    def get_action(self):
        data = self.player_data[self.knife]

        if abs(data['rank']) == 10 and data['token_available'] == []:
            # Skill 10
            self.log.append(_("Inquisitor %s cannot attack") % self.knife)
            is_give = 1
            new_message=True
        else:
            __, selection = yield from single_choice(
                original_message=self.m,
                candidate=[_("Attack"), _("Pass")],
                whitelist=[self.knife],
                text=self.generate_game_message(
                    _("%s select action") % self.knife.mention_html(),
                ),
                static_buttons=self.static_buttons,
                new_message=True,
            )
            is_give = (selection == 1)
            new_message=False

        candidate = [x for x in self.players if x != self.knife]
        __, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[self.knife],
            text=self.generate_game_message(
                _("%s select target") % self.knife.mention_html(),
            ),
            static_buttons=self.static_buttons,
            new_message=new_message,
        )
        target = candidate[selection]

        return target, is_give

    def play_a_round(self):
        self.round += 1
        self.log = []

        target, is_give = yield from self.get_action()

        if is_give:
            self.log.append(_("%s gave the knife to %s.") % (self.knife, target))
            self.knife = target
            self.display_game_message()
            return

        self.victim = target
        self.log.append(_("%s is attacking %s") % (self.knife, self.victim))

        # Interfere (victim may be switched)
        interfered = False

        # Skill 9
        if 'fan' not in self.player_data[self.victim]['item']:
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

            self.log.append(_("%s selected %s token") % (
                self.victim, E[selected_token[0]],
            ))

            # Skills
            if selected_token[-1] == 's':
                func = getattr(self, 'skill' + str(abs(self.player_data[self.victim]['rank'])))
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
                        instruction or (
                            _("%s select token:") % self.victim.mention_html(),
                        ),
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

                update.callback_query.answer(
                    _("Selection invalid, please retry."), True
                )

        # convert skill token to display token
        if selected_token == 's':
            selected_token = str(abs(data['rank']) % 10) + 's'

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
            if 's' in data['token_available']:
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
                candidate=[_("Interfere"), _("Pass")],
                whitelist=candidate,
                blacklist=blacklist,
                id=id,
                text=self.generate_game_message(
                    _("everyone else select interfere or pass")
                ),
                static_buttons=self.static_buttons,
            )

            blacklist.append(update.effective_user)

            if selection == 0: # interfere
                guardians.append(update.effective_user)

            self.log.append(_("%s choosed %s") % (
                update.effective_user,
                [_("Interfere"), _("Pass")][selection],
            ))

            #self.display_game_message()

        # victim decide
        if len(guardians) == 0:
            return

        __, selection = yield from single_choice(
            original_message=self.m,
            candidate=guardians + [_("None")],
            whitelist=[self.victim],
            static_buttons=self.static_buttons,
            text=self.generate_game_message(
                _("%s accept interfere?") % self.victim.mention_html(),
            ),
        )

        if selection == len(guardians): # The (n+1)-th button
            self.log.append(_("%s rejected interference") % self.victim)
        else:
            self.log.append(_("%s accepted %s's interference") % (
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
        yield 

    def skill2(self):
        player = self.victim

        candidate = [x for x in self.players if x != player]

        __, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[player],
            text=self.generate_game_message(
                _("%s a player to trigger skill:") % player.mention_html(),
            ),
            static_buttons=self.static_buttons,
        )
        self.victim = candidate[selection]
        self.log.append(_("%s casted skill on %s") % (player, self.victim))

        for i in [_("1st"), _("2nd")]:
            yield from self.select_and_apply_token(
                instruction=_("%s select %s token:") %
                    (self.victim.mention_html, i),
            )

    def skill3(self):
        player = self.victim
        pdata = self.player_data[player]

        for i in [_("1st"), _("2nd")]:
            candidate = [x
                for x in self.players
                if x != player
                and x not in pdata['checked']
            ]

            if not candidate:
                self.log.append(_("No enough player to be checked."))
                break

            __, selection = yield from single_choice(
                original_message=self.m,
                candidate=candidate,
                whitelist=[player],
                text=self.generate_game_message(
                    _("%s select %s player to check:") %
                        (player.mention_html(), i),
                ),
                static_buttons=self.static_buttons,
            )

            target = candidate[selection]
            pdata['checked'].append(target)
            self.log.append(_("%s checked %s") % (player, target))

    def skill4(self):
        if not self.saved_victim:
            return

        player = self.victim

        data = self.player_data[self.saved_victim]

        if not data['token_used']:
            selection = 0 # kill
            self.log.append(_("%s has no token shown, %s must kill %s") %(
                self.saved_victim, self.victim, self.saved_victim,
            ))
        else:
            __, selection = yield from single_choice(
                original_message=self.m,
                candidate=[_("Kill"), _("Heal")],
                whitelist=[player],
                text=self.generate_game_message(
                    _("%s select kill or heal:") % player.mention_html(),
                ),
                static_buttons=self.static_buttons,
            )

        if selection == 0:
            # Temporarily switch victim
            self.victim = self.saved_victim
            self.log.append(_("%s killed %s") % (player, self.saved_victim))
            yield from self.select_and_apply_token()
            self.victim = player

        else:
            candidate = data['token_used']
            if len(candidate) == 1:
                selected_token = candidate[0]
            else:
                __, selection = yield from single_choice(
                    original_message=self.m,
                    candidate=[E[i[0]] for i in candidate],
                    whitelist=[self.saved_victim],
                    text=self.generate_game_message(
                        _("%s select token for healing:") %
                            self.saved_victim.mention_html(),
                    ),
                    static_buttons=self.static_buttons,
                )

                selected_token = candidate[selection]

            self.log.append(_("%s healed %s") % (player, self.saved_victim))

            data['token_available'].append(selected_token[-1])
            data['token_used'].remove(selected_token)

    def skill5(self):
        player = self.victim

        candidate = [x for x in self.players if x != player]

        __, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[player],
            text=self.generate_game_message(
                _("%s a player to trigger skill:") % player.mention_html(),
            ),
            static_buttons=self.static_buttons,
        )

        self.victim = candidate[selection]
        self.log.append(_("%s casted skill on %s") % (player, self.victim))

        if 's' in self.players_data[self.victim]['token_available']:
            forced = 's'
        else:
            forced = None
        yield from self.select_and_apply_token(forced=forced)

    def skill6(self):
        player = self.victim
        pdata = self.player_data[player]

        if pdata['token_available'] == []:
            self.log.append(
                _("%s already has 3 tokens, not triggering skill") % player,
            )
            return

        color = self.available_shields[pdata['rank']]

        candidate = [x for x in self.players if x != player]

        __, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[player],
            text=self.generate_game_message(
                _("%s give a shield to a player:") % player.mention_html(),
            ),
            static_buttons=self.static_buttons,
        )

        target = candidate[selection]
        data = self.player_data[target]

        if ('sword%s' % color[0]) not in pdata['item']:
            pdata['item'].append('sword%s' % color[0])
        data['item'].append('shield%s' % color[0])

        self.log.append(_("%s gave a shield to %s") % (player, target))

        self.shields.append({'sword': player, 'shield': target})


    def skill6_invalidate(self):
        player = self.victim
        pdata = self.player_data[player]
        color = self.available_shields[pdata['rank']]

        has_sword = False
        for n, i in enumerate(self.shields): # a read-only copy
            if i['sword'] == player:
                has_sword = True
                data = self.player_data[i['shield']]

                pdata['item'].remove('sword%s' % color[0])
                data['item'].remove('shield%s' % color[0])

                del self.shields[n]

        if has_sword:
            self.log.append(_("%s's shields are invalidated") % player)

    def skill6_isprotected(self, player):
        for i in self.shields:
            if i['shield'] == player:
                self.log.append(_("%s is protected by %s's shield") % (
                    player, i['sword'],
                ))
                return True
        return False

    def skill7(self):
        player = self.victim
        target = self.knife

        self.log.append(_("%s casted skill on %s") % (player, target))

        # Temporarily switch victim for select_and_apply_token()
        self.victim = target
        yield from self.select_and_apply_token()
        self.victim = player

    def skill8(self):
        player = self.victim
        pdata = self.player_data[player]

        if 'staff' not in pdata['item']:
            pdata['item'].append('staff')

            # Permanently convert available color tokens to 'white'
            pdata['token_available'] = list(map(
                lambda x: 's' if x == 's' else 'w', pdata['token_available'],
            ))


        candidate = [x
            for x in self.players
            if x != player
            and 'staff' not in self.player_data[x]['item']
        ]

        __, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[player],
            text=self.generate_game_message(
                _("%s give the staff to a player:") % player.mention_html(),
            ),
            static_buttons=self.static_buttons,
        )

        target = candidate[selection]
        data = self.player_data[target]
        data['item'].append('staff')

        # Permanently convert available color tokens to 'white'
        data['token_available'] = list(map(
            lambda x: 's' if x == 's' else 'w', data['token_available'],
        ))

        self.log.append(_("%s gave a staff to %s") % (player, target))

    def skill9(self):
        player = self.victim

        candidate = [x
            for x in self.players
            if x != player
            and 'fan' not in self.player_data[x]['item']
        ]

        __, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[player],
            text=self.generate_game_message(
                _("%s give the fan to a player:") % player.mention_html(),
            ),
            static_buttons=self.static_buttons,
        )

        target = candidate[selection]
        self.player_data[target]['item'].append('fan')
        self.log.append(_("%s gave a fan to %s") % (player, target))

    def skill10(self):
        player = self.victim

        if self.available_curse == []:
            self.log.append(_("%s have no curse books left") % player)
            return

        candidate = [x
            for x in self.players
            if x != player
        ]

        __, selection = yield from single_choice(
            original_message=self.m,
            candidate=candidate,
            whitelist=[player],
            text=self.generate_game_message(
                _("%s give a curse book to a player:") % player,
            ),
            static_buttons=self.static_buttons,
        )
        target = candidate[selection]

        __, selection = yield from single_choice(
            original_message=self.m,
            candidate=list(map(E.get, self.available_curse)),
            whitelist=[target],
            text=self.generate_game_message(
                _("%s select a curse book:") % target.mention_html(),
            ,
            static_buttons=self.static_buttons,
        )

        curse = self.available_curse[selection]
        self.player_data[target]['item'].append(curse)
        self.available_curse.remove(curse)

        self.log.append(_("%s gave a curse book to %s") % (player, target))

    def display_game_message(self, notice=''):
        self.m = self.m.edit_text(
            text=self.generate_game_message(notice),
            parse_mode=ParseMode.HTML,
        )

    def generate_game_message(self, notice=''):
        # log + status + notice

        l = [_(u"<b>round %d</b>") % self.round]
        l += self.log
        l.append('')

        for player in self.players:
            data = self.player_data[player]
            ret = '%-12s' % str(player)[:12]
            for t in data['token_used']:
                ret += E[t[0]]

            ret += E['empty'] * (3 - len(data['token_used']))
            ret += ''.join([E[i] for i in data['item']])
            l.append(u'<pre>%s</pre>' % ret)

        if notice:
            l.append('')
            l.append(u'<b>%s</b>' % notice)

        return u'\n'.join(l)

    def debug(self):
        from pprint import pprint
        pprint(self.player_data)

    def cancel(self):
        if self.round:
            self.display_game_message(_("Game cancelled."))
        else:
            self.m.edit_text(
                text=_("<b>Game cancelled.</b>"),
                parse_mode=ParseMode.HTML,
            )

def start_game(bot, update):
    chat = update.effective_chat

    if chat.type not in ['group', 'supergroup']:
        update.message.reply_text(_("The game must be started in a group."))
        return

    if chat.id in BloodBoundGame.games:
        update.message.reply_text(_("Another game is in progress."))
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
        update.message.reply_text(_("You are not the owner of the game."))
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
            _('You are not in this game, please wait for the next game.'),
            True,
        )

    rank = abs(data['rank'])
    ret = []
    #ret.append(_(u"Player %s") % display_name(user))
    ret.append(_(u"Clan: %s") % E[faction_name(data['rank'])[0]])
    ret.append(_(u"Rank: %d(%s)") % (rank, _(rank_name[rank])))

    icons = ''
    for t in data['token_available']:
        if t == 's':
            icons += E[str(abs(data['rank']) % 10)]
        else:
            icons += E[t]

    ret.append(_(u"Available token: %s") % icons)

    ret.append(_(u"Skill: %s") % _(quick_help[rank]))

    my_index = self.players.index(user)
    after_index = (my_index + 1) % len(self.players)
    player_after = self.players[after_index]
    rank = self.player_data[player_after]['rank']
    after_faction = E[['b', 'r'][(rank > 0) ^ (abs(rank) == 3)]]
    ret.append(_(u"Next player (%s) is %s") % (
        display_name(player_after), after_faction,
    ))

    if data['checked']:
        ret.append(_(u"Checked players:"))
        for player in data['checked']:
            rank = self.player_data[player]['rank']
            ret.append('%s: %s%s' % (
                player,
                E[faction_name(rank)[0]],
                E[str(abs(rank) % 10)],
            ))

    return query.answer(u'\n'.join(ret), True)

def help(bot, update):
    update.message.reply_text(_("Use /start_game to test this bot."))

def main():
    updater = Updater(os.environ['BOT_TOKEN'])

    updater.dispatcher.add_handler(InteractiveHandler(
        start_game,
        entry_points = [
            CommandHandler('start_game', None),
        ],
        fallbacks = [
            CommandHandler('cancel', cancel_game),
            CallbackQueryHandler(info_button, pattern=r'^info$'),
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
        )) + 'api/' + os.environ['BOT_TOKEN']

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
        print('Webhook info:')
        import pprint; pprint.pprint(str(info))

    else:
        updater.start_polling(clean=True, timeout=10)

    print('Blood Bound Bot ready for serving!')
    sys.stdout.flush()

    updater.idle()

if __name__ == '__main__':
    main()
