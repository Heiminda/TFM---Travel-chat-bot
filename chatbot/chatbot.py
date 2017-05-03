#coding: utf-8

import sys
import time
import telepot.helper
import pickle
import pandas as pd
import numpy as np
import pymongo
import telepot
import datetime

from message_handler_bot import *

from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, ForceReply
from telepot.delegate import (
    per_chat_id, per_application, call, create_open, include_callback_query_chat_id, pave_event_space)

#DATABASE_FILE = "../trivago_data/pandas_dbs/dataset.pkl"
#db = pd.read_pickle(DATABASE_FILE)

options_central = ["Much","Not much","Outskirts","Don't care"]
options_touristic = ["Yes", "Not really", "Don't care"]

###################################################################################

class chat_state:
    NEW                 = "1"
    WELCOME             = "2"
    STARTED             = "3"
    CITY                = "4"
    ROOM                = "5"
    NEIGHBOURHOOD       = "6"
    NEIGHBOURHOOD_YES   = "7"
    CENTRALITY          = "8"
    TOURISTIC_ZONE      = "9"
    PRICE               = "10"
    PRICE_YES           = "11"
    CONFIRMING          = "12"
    RECOMMENDATION      = "13"

class command:
    START   = '/start'
    QUIT    = '/q'


#####################################################################################

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


class DatabaseRetrieving(object):

    def __init__(self):
        self._db = pd.read_pickle("../trivago_data/pandas_dbs/dataset_visualization.pkl")

    # Return all cities in a list of strings
    def get_cities(self):
        return list(set(self._db.city))

    def get_neighbourhoods_from_city(self, city):
        return list(self._db[self._db.city == city].groupby("neighbourhood").count()["name"].sort_values(ascending=False).index)

    def get_neighbourhoods_answers_from_city(self, city):
        neighs = list(self._db[self._db.city == city].groupby("neighbourhood").count()["name"].sort_values(ascending=False).index)
        return [str(i) for i in range(len(neighs))]

    def get_neighbourhood_from_index(self, city, index):
        neighs = list(self._db[self._db.city == city].groupby("neighbourhood").count()["name"].sort_values(ascending=False).index)
        return neighs[index]

    def get_prices_from_city(self, city):
        return np.asarray(self._db[self._db.city == city].price).astype(np.float64)

    def city2int(self, city):
        if city.lower() == "barcelona":
            return 0


""" This database should be used to store user activity logs """
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

###########################################################################################

""" This class is for handling different chat states """
class Chat(object):

    def __init__(self, chat_id):
        self._chat_id = chat_id
        self._state = chat_state.NEW
        self._city = None

    def change_state(self, new_state):
        self._state = new_state

    def get_state(self):
        return self._state

    def change_city(self, city):
        self._city = city

    def get_city(self):
        return self._city

""" Collection of chats """
class ChatCollection(object):

    def __init__(self):
        self._chats = {} # dict of chat_id:chat_object

    # put new chat from chat_id
    def put(self, chat_id):
        if chat_id not in self._chats.keys():
            self._chats[chat_id] = Chat(chat_id)
            self._chats[chat_id].change_state(chat_state.NEW)

    # drop chat from chat object (not efficient)
    def drop_from_chat(self, chat):
        if chat in self._chats.values():
            r = dict(self._chats)
            for k,v in r.iteritems():
                if v == chat:
                    del r[k]
                    break
            self._chats = r

    def drop_from_id(self, chat_id):
        if chat_id in self._chats.keys():
            r = dict(self._chats)
            del r[chat_id]
            self._chats = r

    # get chat from chat_id
    def get(self, chat_id):
        return self._chats[chat_id]

    def get_chats_ids(self):
        return self._chats.keys()

    def get_chat_state(self, chat_id):
        return self._chats[chat_id].get_state()

    # NOT EFFICIENT
    def modify_state_from_chat(self, chat, new_state):
        for k,v in self._chats.iteritems():
            if v == chat:
                self._chats[k].change_state(new_state)
                break

    # EFFICIENT WAY TO CHANGE STATE
    def modify_state_from_id(self, chat_id, new_state):
        self._chats[chat_id].change_state(new_state)

    def set_city_to_chat(self, chat_id, city):
        self._chats[chat_id].change_city(city)

    def get_city_from_chat(self, chat_id):
        return self._chats[chat_id].get_city()

class FeatureFilter(object):

    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.features = {"city":None, "neighbourhood":None, "room":None, "centrality":None, "touristic":None, "price":None}

    def get_filter_features(self):
        return self.features

    def print_filters(self):
        return print_features(self.features)

    def assign_value(self, key, value):
        self.features[key] = value

    def delete_data(self):
        self.chat_id = None
        self.features = dict()


####################################################################################

# Accept commands from owner.
class MessageHandler(telepot.helper.ChatHandler):

    def __init__(self, *args, **kwargs):
        super(MessageHandler, self).__init__(*args, **kwargs)
        self._db_retrieving = DatabaseRetrieving()
        self._db_storing = DatabaseStoring()
        self._chats = ChatCollection()
        self._bot = self.bot
        self._msg_inline_keyboard = None
        self.feature_filter = FeatureFilter(args[0][1]["chat"]["id"])

    def is_price_range(self, msg):
        try:
            values = msg.split(" ")
            if int(values[0]) and int(values[1]):
                if int(values[0]) < int(values[1]):
                    return True
        except Exception:
            return False

    def parse_price_range(self, msg):
        values = msg.split(" ")
        return (float(values[0]),float(values[1]))

    datetime.datetime.fromtimestamp(
        int("1284101485")
    ).strftime('%Y-%m-%d %H:%M:%S')

    # This method deals with text messages
    def on_chat_message(self, msg):
        content_type, chat_type, chat_id, msg_date, msg_id = telepot.glance(msg, long=True)
        print('Chat message:', content_type, chat_type, chat_id, datetime.datetime.fromtimestamp(int(msg_date)).strftime('%Y-%m-%d %H:%M:%S'), msg_id)

        if content_type != 'text':
            return

        com = msg['text'].lower()

        # HANDLE NEW CHAT
        chat_not_new = True

        if chat_id not in self._chats.get_chats_ids():
            self._chats.put(chat_id)
            self._bot.sendMessage(chat_id, welcome_message(), parse_mode="Markdown")
            chat_not_new =  False

        if chat_not_new:

            city_chat = self._chats.get_city_from_chat(chat_id)

            # START QUESTION
            if self._chats.get_chat_state(chat_id) == chat_state.NEW:

                if com == command.START:
                    # if started, we go to city question
                    self._chats.modify_state_from_id(chat_id, chat_state.CITY)
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text=city, callback_data=city) for city in self._db_retrieving.get_cities() ],
                             ])
                    self._bot.sendMessage(chat_id, hotel_rec_starter(), parse_mode="Markdown")
                    self._msg_inline_keyboard = bot.sendMessage(chat_id, ask_city_question(), parse_mode="Markdown",reply_markup=markup)

            # NEIGHBOURHOOD QUESTION
            elif self._chats.get_chat_state(chat_id) == chat_state.NEIGHBOURHOOD_YES:

                if com in self._db_retrieving.get_neighbourhoods_answers_from_city(city_chat):

                    # RECOMMENDATION FILTER
                    self.feature_filter.assign_value("neighbourhood",self._db_retrieving.get_neighbourhood_from_index(city_chat, int(com)))

                    # show feedback to user
                    msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                    self._bot.editMessageText(msg_idf, "We've got the neighbourhood." , parse_mode="Markdown")
                    self._bot.sendMessage(chat_id, "Okay!")

                    # follow the process
                    self._chats.modify_state_from_id(chat_id, chat_state.CENTRALITY)
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text=options_central[0], callback_data=options_central[0]), InlineKeyboardButton(text=options_central[1], callback_data=options_central[1])],
                                 [InlineKeyboardButton(text=options_central[2], callback_data=options_central[2]), InlineKeyboardButton(text=options_central[3], callback_data=options_central[3])],
                             ])
                    self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_central(), parse_mode="Markdown", reply_markup=markup)

                else:
                    self._bot.sendMessage(chat_id, "Ouch, you chose a wrong option. Please try again.", parse_mode="Markdown")

            # PRICE QUESTION
            if self._chats.get_chat_state(chat_id) == chat_state.PRICE_YES:

                if self.is_price_range(com):

                    self._bot.sendMessage(chat_id, "Okay, correct price format!", parse_mode="Markdown")
                    self._chats.modify_state_from_id(chat_id, chat_state.CONFIRMING)

                    # RECOMMENDATION FILTER
                    self.feature_filter.assign_value("price",self.parse_price_range(com))

                    # FOLLOW PROCESS HERE
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="Yes", callback_data="yes_change"), InlineKeyboardButton(text="No", callback_data="no_change")],
                             ])
                    self._msg_inline_keyboard = self._bot.sendMessage(chat_id, self.feature_filter.print_filters(), parse_mode="Markdown", reply_markup=markup)

                else:
                    self._bot.sendMessage(chat_id, price_format_wrong(), parse_mode="Markdown")

            # QUIT MODE
            if com == command.QUIT:

                if int(self._chats.get_chat_state(chat_id)) < 3:
                    self._bot.sendMessage(chat_id, "I can't do this option because you just started the process.\
                                                    \nIf you don't want to interact with the bot just ignore it, he will be here anytime.", parse_mode="Markdown")
                else:
                    # show feedback to user
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="Yes", callback_data="yes_quit"), InlineKeyboardButton(text="No", callback_data="no_quit")],
                             ])
                    self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_quit(), parse_mode="Markdown", reply_markup=markup)


    # This method deals with callback messages
    def on_callback_query(self, msg):
        query_id, chat_id, data = telepot.glance(msg, flavor='callback_query')
        print('Callback query:', query_id, chat_id, data)

        if int(self._chats.get_chat_state(chat_id)) > 4:
            city = self._chats.get_city_from_chat(chat_id)

        # CITY QUESTION
        if self._chats.get_chat_state(chat_id) == chat_state.CITY:

            if data in self._db_retrieving.get_cities():

                # RECOMMENDATION FILTER HERE
                self.feature_filter.assign_value("city",self._db_retrieving.city2int(data))

                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Got it, City: *%s*" % data, parse_mode="Markdown")
                self._chats.set_city_to_chat(chat_id,data)

                # follow the process
                self._chats.modify_state_from_id(chat_id, chat_state.ROOM)
                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="Individual", callback_data="Individual"), InlineKeyboardButton(text="Double", callback_data="Double"), InlineKeyboardButton(text="Triple/more", callback_data="More")],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_roomtype_question(), parse_mode="Markdown", reply_markup=markup)

        # ROOM QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.ROOM:

            if data == "Individual" or data == "Double" or data == "More":

                # RECOMMENDATION FILTER HERE
                self.feature_filter.assign_value("room",data)

                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Got it, Room type: *%s*" % data, parse_mode="Markdown")

                # follow the process
                self._chats.modify_state_from_id(chat_id, chat_state.NEIGHBOURHOOD)
                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="Yes", callback_data="yes_neigh"), InlineKeyboardButton(text="No", callback_data="no_neigh")],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_neighbourhood_1(), parse_mode="Markdown", reply_markup=markup)

        # NEIGHBOURHOOD QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.NEIGHBOURHOOD:

            if data == "yes_neigh":
                # show feedback to user
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Okay.", parse_mode="Markdown")
                # follow the process
                self._chats.modify_state_from_id(chat_id, chat_state.NEIGHBOURHOOD_YES)
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_neighbourhood_2(self._db_retrieving.get_neighbourhoods_from_city(city)), parse_mode="Markdown")

            elif data == "no_neigh":
                # show feedback to user
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "No problem.")

                # follow the process
                self._chats.modify_state_from_id(chat_id, chat_state.CENTRALITY)
                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text=options_central[0], callback_data=options_central[0]), InlineKeyboardButton(text=options_central[1], callback_data=options_central[1])],
                             [InlineKeyboardButton(text=options_central[2], callback_data=options_central[2]), InlineKeyboardButton(text=options_central[3], callback_data=options_central[3])],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_central(), parse_mode="Markdown", reply_markup=markup)

        # CENTRALITY QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.CENTRALITY:

            if data in options_central:

                # show feedback to user
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Got it, Centrality: *%s*" % data , parse_mode="Markdown")

                self.feature_filter.assign_value("centrality", data if data in options_central[:-1] else None)

                # follow the process
                self._chats.modify_state_from_id(chat_id, chat_state.TOURISTIC_ZONE)
                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text=options_touristic[0], callback_data=options_touristic[0]),
                              InlineKeyboardButton(text=options_touristic[1], callback_data=options_touristic[1]),
                              InlineKeyboardButton(text=options_touristic[2], callback_data=options_touristic[2])],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_touristic(), parse_mode="Markdown", reply_markup=markup)

        # TOURISTIC QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.TOURISTIC_ZONE:

            if data in options_touristic:
                idx = options_touristic.index(data)
                # show feedback to user
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Got it, Touristic: *%s*" % data , parse_mode="Markdown")

                # handle different types of Touristic location
                self.feature_filter.assign_value("touristic", data if data in options_touristic[:-1] else None)

                # follow the process
                self._chats.modify_state_from_id(chat_id, chat_state.PRICE)

                self._bot.sendMessage(chat_id, price_range_stats(self._db_retrieving.get_prices_from_city(self._chats.get_city_from_chat(chat_id))), parse_mode="Markdown")
                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="Yes", callback_data="yes_price"), InlineKeyboardButton(text="No", callback_data="no_price")],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_if_price_range(), parse_mode="Markdown", reply_markup=markup)

        # PRICE QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.PRICE:

            if data == "yes_price" or data == "no_price":

                if data == "yes_price":

                    # show feedback to user
                    msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                    bot.editMessageText(msg_idf, "Got it. User wants to specify a *price range*.", parse_mode="Markdown")

                    # follow process
                    self._chats.modify_state_from_id(chat_id, chat_state.PRICE_YES)
                    self._bot.sendMessage(chat_id, price_format(), parse_mode="Markdown")

                elif data == "no_price":

                    # show feedback to user
                    msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                    bot.editMessageText(msg_idf, "Got it. No problem.", parse_mode="Markdown")

                    # follow process
                    self._chats.modify_state_from_id(chat_id, chat_state.CONFIRMING)

                    markup = InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="Yes", callback_data="yes_change"), InlineKeyboardButton(text="No", callback_data="no_change")],
                             ])
                    self._msg_inline_keyboard = self._bot.sendMessage(chat_id, self.feature_filter.print_filters(), parse_mode="Markdown", reply_markup=markup)

        # CHANGE FILTERING QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.CONFIRMING:

            if data == "yes_change" or data == "no_change":

                if data == "yes_change":

                    # reset whole process and ask first question (city) again
                    msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                    bot.editMessageText(msg_idf, "Okay, now you will be asked all the questions again.\n", parse_mode="Markdown")

                    self.feature_filter.delete_data()

                    self._chats.modify_state_from_id(chat_id, chat_state.CITY)
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text=city, callback_data=city) for city in self._db_retrieving.get_cities() ],
                             ])
                    self._bot.sendMessage(chat_id, hotel_rec_starter(), parse_mode="Markdown")
                    self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_city_question(), parse_mode="Markdown",reply_markup=markup)

                else:
                    # RECOMMEND HOTEL HERE
                    self._bot.sendMessage(chat_id, "Great! Please, wait until we process your personalized hotel recommendations...\n", parse_mode="Markdown")
                    self._chats.modify_state_from_id(chat_id, chat_state.RECOMMENDATION)

                    # TODO
                    print "HELLO RECOMMENDATION"

        # QUIT THE PROCESS
        if data == u"yes_quit" or data == u"no_quit":

            if data == u"yes_quit":
                # delete all data from filter
                self.feature_filter.delete_data()
                # delete chat
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "...", parse_mode="Markdown")
                self._chats.drop_from_id(chat_id)
                self._bot.sendMessage(chat_id, bye_message(), parse_mode="Markdown")

            else:
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Thank you for keep trusting in us!\nPlease, now you should continue from the last question asked.", parse_mode="Markdown")


############################################################################################


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


####################################################################################


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



class YogiBot(telepot.DelegatorBot):

    def __init__(self, token):

        self._seen = set()

        super(YogiBot, self).__init__(token, [
            # Here is a delegate to specially handle owner commands.
            include_callback_query_chat_id(
                pave_event_space())(
                    per_chat_id(), create_open, MessageHandler, timeout = 99999),
        ])


if __name__=="__main__":

    TOKEN = "351129972:AAEFuBELNKPSEmWsi0k7BzxQGZphChBpknI"

    bot = YogiBot(TOKEN)

    # if updates, clear them
    updates = bot.getUpdates()

    if updates:
        last_update_id = updates[-1]['update_id']
        bot.getUpdates(offset=last_update_id+1)

    bot.message_loop(run_forever='Listening ...')
