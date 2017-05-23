#coding: utf-8

import sys
import telepot
from telepot.delegate import (
    per_chat_id_in, per_application, call, create_open, pave_event_space)

import pymongo

##################################################################################

# Connection to Mongo DB
def _connect_to_database():
    try:
        conn = pymongo.MongoClient('localhost:27017')
        print "Connected successfully to MongoDB!"
    except pymongo.errors.ConnectionFailure, e:
        print "Could not connect to MongoDB: %s" % e
        return None
    try:
        db = conn["DatabotDB"]
    except pymongo.errors.PyMongoError, e:
        print "Could not connect to database with name",database_name
        return None
    return db.TextData

""" This class will be used as a database operation center """
class DatabaseStoring(object):

    def __init__(self):
        self._db_mongo = _connect_to_database()
        self._db = {}
        # self._db_file = open(database_name,"w")

    # Insert data to Database
    def insert(self, msg):
        self._db_mongo.insert_one(msg)

        chat_id = msg["chat"]["id"]

        if chat_id not in self._db:
            self._db[chat_id] = []

        text = msg['text'].lower()

        self._db[chat_id].append(text)
        # self._db_file.write(str(chat_id) + "\t" + text)


##################################################################################

""" This class is for handling different chat states """
class Chat(object):

    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.is_new = True

    def get_chat_state(self):
        return self.state

    def change_state(self):
        self.state = False

class ChatCollection(object):

    def __init__(self):
        self.chats = []

    def put(self, chat):
        if chat not in self.chats:
            self.chats.append(chat)

    def drop(self, chat):
        if chat in self.chats:
            self.chats.remove(chat)

    def get_chats_ids(self):
        return [chat.chat_id for chat in self.chats]

    # set is_new state of chat to False
    def modify_chat_state(self,chat):
        idx = self.chats.index(chat)
        self.chats[idx].change_state()

####################################################################################

# Accept commands from owner.
class MessageHandler(telepot.helper.ChatHandler):

    def __init__(self, seed_tuple, store, **kwargs):
        super(MessageHandler, self).__init__(seed_tuple, **kwargs)
        self._store = store

    # This method deals with text messages
    def on_chat_message(self, msg):
        content_type, chat_type, chat_id, msg_date, msg_id = telepot.glance(msg, long=True)
        print('Chat:', content_type, chat_type, chat_id, msg_date, msg_id)

        if content_type != 'text':
            return

        text = msg['text'].lower()


    # This method deals with callback messages
    def on_callback_query(self, msg):
        query_id, from_id, data = telepot.glance(msg, flavor='callback_query')
        print('Callback query:', query_id, from_id, data)


class MessageSaver(telepot.helper.Monitor):

    # exclude is/are those id/ids that the program want to exclude from saving data
    def __init__(self, seed_tuple, store, chats, exclude):
        # The `capture` criteria means to capture all messages.
        super(MessageSaver, self).__init__(seed_tuple, capture=[[lambda msg: not telepot.is_event(msg)]])
        self._bot = seed_tuple[0]
        self._store = store
        self._chats = chats
        self._exclude = exclude

    # Store every message, except those whose sender is in the exclude list, or non-text messages.
    def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)

        if chat_id in self._exclude:
            print('Chat id %d is excluded.' % chat_id)
            return

        if content_type != 'text':
            print('Content type %s is ignored.' % content_type)
            return

        chat_not_new = "True"

        if chat_id not in self._chats.get_chats_ids():
            new_chat = Chat(chat_id)
            self._chats.put(new_chat)
            chat_not_new = False

        if chat_not_new:
            print('From chat id %d. Storing message: %s.' % (chat_id, msg["text"].lower()))
            self._store.insert(msg)
            # Now we should store the data
            self._bot.sendMessage(chat_id, "We have stored your answer. Thank you!")
        else:
            self._chats.modify_chat_state(new_chat)

####################################################################################

import threading

class CustomThread(threading.Thread):

    def start(self):
        print('CustomThread starting ...')
        super(CustomThread, self).start()


# Note how this function wraps around the `call()` function below to implement
# a custom thread for delegation.
def custom_thread(func):
    def f(seed_tuple): # seed_tuple should be of the form (bot, message, seed)
        target = func(seed_tuple)

        if type(target) is tuple:
            run, args, kwargs = target
            t = CustomThread(target=run, args=args, kwargs=kwargs)
        else:
            t = CustomThread(target=target)

        return t
    return f

####################################################################################


class Databot(telepot.DelegatorBot):

    def __init__(self, token, owner_id):

        self._owner_id = owner_id
        self._seen = set()
        self._store = DatabaseStoring()
        self._chats = ChatCollection()

        super(Databot, self).__init__(token, [
            # Here is a delegate to specially handle owner commands.
            pave_event_space()(
                per_chat_id_in([owner_id]), create_open, MessageHandler, self._store, timeout=20),

            # Only one MessageSaver is ever spawned for entire application.
            (per_application(), create_open(MessageSaver, self._store, self._chats, exclude=[owner_id])),

            # For senders never seen before, send him a welcome message.
            (self._is_newcomer, custom_thread(call(self._send_welcome))),
        ])


    # seed-calculating function: use returned value to indicate whether to spawn a delegate
    def _is_newcomer(self, msg):
        if telepot.is_event(msg):
            return None

        chat_id = msg['chat']['id']
        if chat_id == self._owner_id:  # Sender is owner
            return None  # No delegate spawned

        if chat_id in self._seen:  # Sender has been seen before
            return None  # No delegate spawned

        self._seen.add(chat_id)
        return []  # non-hashable ==> delegates are independent, no seed association is made.


    def _send_welcome(self, seed_tuple):

        msg = "THE WELCOME MESSAGE SHOULD GO HERE"

        chat_id = seed_tuple[1]['chat']['id']

        self.sendMessage(chat_id, 'Hello!')


TOKEN = "351129972:AAEFuBELNKPSEmWsi0k7BzxQGZphChBpknI"
OWNER_ID = 351129972

bot = Databot(TOKEN, OWNER_ID)

# if updates, clear them
updates = bot.getUpdates()

if updates:
    last_update_id = updates[-1]['update_id']
    bot.getUpdates(offset=last_update_id+1)


bot.message_loop(run_forever='Listening ...')
