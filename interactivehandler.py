
import inspect
import functools
import threading

from telegram.ext import Handler

class ConversationCancelled(Exception):
    def __init__(self, update):
        self.update = update

class InteractiveHandler(Handler):
    def __init__(self,
        callback, # a generator function (i.e. has yield statement within it)
        entry_points, # Handler subclasses with optional perdictors
        fallbacks = [], # Handler subclasses available globally (with callbacks)
        per_chat=True,
        per_user=True,
        per_message=False,
    ):

        self.callback = callback

        self.entry_points = entry_points
        self.fallbacks = fallbacks

        self.per_chat = per_chat
        self.per_user = per_user
        self.per_message = per_message

        self.conversations = {}

        if not inspect.isgeneratorfunction(self.callback):
            raise ValueError("'callback' must be a generator function (i.e. has yield statement within it)")

        if not any((self.per_user, self.per_chat, self.per_message)):
            raise ValueError("'per_user', 'per_chat' and 'per_message' can't all be 'False'")

        if self.per_message and not self.per_chat:
            logging.warning("If 'per_message=True' is used, 'per_chat=True' should also be used, "
                            "since message IDs are not globally unique.")

    def _get_key(self, update):
        chat = update.effective_chat
        user = update.effective_user

        key = []

        if self.per_chat:
            key.append(chat.id)

        if self.per_user and user is not None:
            key.append(user.id)

        if self.per_message:
            key.append(update.callback_query.inline_message_id
                       or update.callback_query.message.message_id) 

        return tuple(key)
        
    def check_update(self, update):
        #import ipdb; ipdb.set_trace()
        context = self.conversations.get(self._get_key(update))

        if not context:
            # No conversation yet, check entrypoints
            for i in self.entry_points:
                if i.check_update(update):
                    # Check optional predictor here
                    if not callable(i.callback) or i.callback(None, update):
                        # Record selected Handler first,
                        # and coroutine will be created in handle_update
                        self.conversations[self._get_key(update)] = {
                            'coroutine': None,
                            'next': self.entry_points,
                            'current_handler': i,
                        }
                        return True

            # Ignore any fallbacks
            return False

        # We have a conversation, check its next step
        context['current_handler'] = None
        for i in context['next']:
            if i.check_update(update):
                # Check optional predictor here
                if not callable(i.callback) or i.callback(None, update):
                    context['current_handler'] = i
                    return True

        # Finally check all the fallbacks
        for i in self.fallbacks:
            if i.check_update(update):
                return True

        return False

    def handle_update(self, update, dispatcher):
        #import ipdb; ipdb.set_trace()
        context = self.conversations[self._get_key(update)]

        if not context['coroutine']:
            # No conversation yet, hit one of the entrypoints
            context['coroutine'] = self.callback(dispatcher.bot, update)
            context['lock'] = threading.Lock()

            try:
                context['lock'].acquire()
                yielded = next(context['coroutine'])
                print(yielded)
            except StopIteration:
                del self.conversations[self._get_key(update)]
                return 
            finally:
                context['lock'].release()

            context['next'] = yielded

        elif context['current_handler']:
            # Has conversation, check next then fallback
            #import ipdb; ipdb.set_trace()
            try:
                context['lock'].acquire()
                yielded = context['coroutine'].send(update)
            except StopIteration:
                del self.conversations[self._get_key(update)]
                return
            finally:
                context['lock'].release()

            context['next'] = yielded

        else:
            for i in self.fallbacks:
                if i.check_update(update):
                    context['lock'].acquire()
                    # User can call update.cancel_current_conversation()
                    # to shutdown current conversation cleanly (i.e. the coroutine)
                    update.cancel_current_conversation = (
                            functools.partial(self.cancel_current_conversation, update)
                    )
                    i.handle_update(update, dispatcher)
                    context['lock'].release()
                    return

    def cancel_current_conversation(self, update):
        context = self.conversations[self._get_key(update)]

        try:
            context['coroutine'].throw(ConversationCancelled(update))
        except StopIteration:
            pass

        del self.conversations[self._get_key(update)]
