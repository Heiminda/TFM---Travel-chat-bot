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
import distance
from unidecode import unidecode

from message_handler_bot import *
from hotel_recommender import HotelRecommender
from flight_predictor import FlightPredictor
from sentiment_analyser import SentimentAnalyser
import model

from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, ForceReply
from telepot.delegate import (
    per_chat_id, per_application, call, create_open, include_callback_query_chat_id, pave_event_space)


###################################################################################

options_central = ["Much","Not much","Not at all","Don't care"]

class chat_state:
    # USER SETTINGS
    NEW                     = "000"
    FIRST_QUESTION          = "001"
    QUITTING                = "098"
    REPEATING               = "099"
    # FLIGHT STATES
    FLIGHT_FROM             = "101"
    FLIGHT_FROM_AIRPORT     = "102"
    FLIGHT_TO               = "103"
    FLIGHT_TO_AIRPORT       = "104"
    FLIGHT_WHEN             = "105"
    FLIGHT_ONLY_FINISHED    = "110"
    # HOTEL STATES
    CITY                    = "204"
    ROOM                    = "205"
    NEIGHBOURHOOD           = "206"
    NEIGHBOURHOOD_YES       = "207"
    NEIGHBOURHOOD_YES_LIST  = "208"
    NEIGHBOURHOOD_YES_WRITE = "209"
    CENTRALITY              = "210"
    TOURISTIC_ZONE          = "211"
    PRICE                   = "212"
    PRICE_YES               = "213"
    CONFIRMING              = "214"
    RECOMMENDATION          = "215"
    REVIEW_USER             = "216"

class auxiliar_state:
    FLIGHT_FROM_WRITE_NEW           = "190"
    FLIGHT_FROM_WRITE_NOTNEW        = "191"
    FLIGHT_TO_WRITE_NEW             = "194"
    FLIGHT_TO_WRITE_NOTNEW          = "195"
    NEIGH_WRITE_NEW                 = "280"
    NEIGH_WRITE_NOTNEW              = "281"
    FINISHED                        = "282"

class command:
    START   = '/start'
    QUIT    = '/quit'
    REPEAT  = '/repeat'

#####################################################################################

def find_nearest(input, list_from, threshold = 0.005):
    w, h = len(list_from), len(input.split())
    min_dist_matrix = [[0 for x in range(w)] for y in range(h)]

    # Measure distances of all combinations
    for word,k in zip(input.split(), range(len(input.split()))):
        for element, i in zip(list_from, range(len(list_from))):
            words_element = element.split()
            dist = [None]*len(words_element)
            for word_element,j in zip(words_element, range(len(words_element))):
                dist[j] = distance.levenshtein(input, word_element)
            min_dist_matrix[k][i] = min(dist)
    lev_dist = np.sum(min_dist_matrix, axis = 0)
    idxs = lev_dist.argsort()[:3] # return three most similar elements from list_from
    lev_dist_norm = lev_dist / float(sum(lev_dist))

    if abs(lev_dist_norm[idxs[0]] - lev_dist_norm[idxs[1]]) > threshold:
        return list_from[idxs[0]]
    elif abs(lev_dist_norm[idxs[1]] - lev_dist_norm[idxs[2]]) > threshold:
        return list(np.array(list_from)[idxs[0:1]])
    else:
        return list(np.asarray(list_from)[idxs])

class DatabaseRetrieving(object):

    def __init__(self):
        self._db = pd.read_csv("trivago.csv", delimiter="\t", header=0).ix[:,1:]

    # Return all cities in a list of strings
    def get_cities(self):
        return list(set(self._db.city_name))

    def get_neighbourhoods_from_city(self, city):
        return list(self._db[self._db.city_name == city].groupby("neighbourhood").count()["hotel_name"].sort_values(ascending=False).index)

    def get_neighbourhoods_answers_from_city(self, city):
        neighs = list(self._db[self._db.city_name == city].groupby("neighbourhood").count()["hotel_name"].sort_values(ascending=False).index)
        return [str(i) for i in range(len(neighs))]

    def get_neighbourhood_from_index(self, city, index):
        neighs = list(self._db[self._db.city_name == city].groupby("neighbourhood").count()["hotel_name"].sort_values(ascending=False).index)
        return neighs[index]

    def get_prices_from_features(self, features):
        # filter db acc to features
        db = self._db.copy()
        # filter city
        db = db[db.city_int == features["cityInt"]]
        # filter neighbourhood, if any
        if features["neighbourhood"] is not None:
            db = db[db["neighbourhood"] == features["neighbourhood"]]
        # filter centrality
        if features["centrality"] != options_central[-1]:
            if features["centrality"] == options_central[0]:
                db = db[db['is_hotel_very_centric'] == True]
            elif features["centrality"] == options_central[1]:
                db = db[db['is_hotel_centric'] == True]
            elif features["centrality"] == options_central[2]:
                db = db[(db['is_hotel_very_centric'] == False) & (db['is_hotel_centric'] == False)]

        return np.asarray(db.price).astype(np.float64)

    def city2int(self, city):
        if city.lower() == "barcelona":
            return 2

    def find_number_hotels_by_cities(self):
        """Returns a dictionary in which each key has its number of hotels as value"""
        return dict(self._db.groupby("city_name").count()["hotel_name"])

    def find_number_hotels_by_neigh(self, len_list=100, neighs=None):
        if len_list > 1 and len_list < 4:
            return dict(self._db[self._db.neighbourhood.isin(neighs)].groupby("neighbourhood").count()["hotel_name"])
        if len_list == 1 and isinstance(neighs, str):
            return self._db[self._db.neighbourhood == neighs].count()["hotel_name"]
        else:
            return dict(self._db.groupby("neighbourhood").count()["hotel_name"])

    def find_number_hotels_by_centrality(self):
        d = dict()
        for opt in options_central:
            if opt == options_central[0]:
                d[opt] = self._db[self._db["is_hotel_very_centric"] == True].count()["hotel_name"]
            if opt == options_central[1]:
                d[opt] = self._db[self._db["is_hotel_centric"] == True].count()["hotel_name"]
            if opt == options_central[2]:
                d[opt] = self._db[(self._db['is_hotel_very_centric'] == False) & (self._db['is_hotel_centric'] == False)].count()["hotel_name"]
            if opt == options_central[-1]:
                d[opt] = self._db.shape[0]
        return d

############################################################################################

class MongoHandler(object):

    def __init__(self, dbname, col_name):
        self.db = self.connect_to_database(dbname, col_name)

    # Connection to Mongo DB
    def connect_to_database(self, dbname, col_name):
        try:
            conn = pymongo.MongoClient('localhost:27017')
            print "Connected successfully to MongoDB!"
        except pymongo.errors.ConnectionFailure, e:
            print "Could not connect to MongoDB: %s" % e
            return None
        try:
            db = conn[dbname]
        except pymongo.errors.PyMongoError, e:
            print "Could not connect to database with name", dbname
            return None
        return db[col_name]

    # Insert data to Database
    def insert(self, content):
        self.db.insert_one(content)


class LogSaver(telepot.helper.Monitor):

    # exclude is/are those id/ids that the program want to exclude from saving data
    def __init__(self, seed_tuple, chats):
        # The `capture` criteria means to capture all messages.
        super(LogSaver, self).__init__(seed_tuple, capture=[[lambda msg: not telepot.is_event(msg)]])
        self._bot = seed_tuple[0]
        self._log = MongoHandler(dbname="TravelChatbot_UserLogs", col_name="Logs")
        self._chats = chats

    # Store every message, except those whose sender is in the exclude list, or non-text messages.
    def on_chat_message(self, msg):
        content_type, chat_type, chat_id, msg_date, msg_id = telepot.glance(msg, long=True)
        print('Chat message:', unidecode(msg["from"]["first_name"]), chat_id, datetime.datetime.fromtimestamp(int(msg_date)).strftime('%Y-%m-%d %H:%M:%S'), msg["text"])

        if chat_id in self._chats.get_chats_ids():
            c_state  = self._chats.get_chat_state(chat_id) # chat state
            a_state  = self._chats.get_chat_aux_state(chat_id) # auxiliar state

            if c_state != chat_state.REVIEW_USER or a_state != auxiliar_state.FINISHED:
                content = {
                            "chat_id"   : msg["chat"]["id"],
                            "username"  : unidecode(msg["from"]["first_name"]),
                            "date"      : int(msg["date"]),
                            "content"   : msg["text"].lower(),
                            "user_id"   : msg["from"]["id"],
                            "chat_state": c_state,
                            "aux_state" : a_state
                            }
                self._log.insert(content)

    def on_callback_query(self, msg):
        query_id, chat_id, data = telepot.glance(msg, flavor='callback_query', long=True)
        print('Callback query:', unidecode(msg["from"]["first_name"]), chat_id, datetime.datetime.fromtimestamp(int(msg["message"]["date"])).strftime('%Y-%m-%d %H:%M:%S'), data)

        if chat_id in self._chats.get_chats_ids():
            c_state = self._chats.get_chat_state(chat_id)
            a_state = self._chats.get_chat_aux_state(chat_id)

            if c_state != chat_state.REVIEW_USER or a_state != auxiliar_state.FINISHED:
                content = {
                            "chat_id"   : msg["message"]["chat"]["id"],
                            "username"  : unidecode(msg["from"]["first_name"]),
                            "date"      : int(msg["message"]["date"]),
                            "content"   : msg["data"],
                            "user_id"   : msg["from"]["id"],
                            "chat_state": c_state,
                            "aux_state" : a_state
                          }
                self._log.insert(content)

####################################################################################


""" This class is for handling different chat states """
class Chat(object):

    def __init__(self, chat_id):
        self._chat_id = chat_id
        self._state = chat_state.NEW
        self._auxstate = chat_state.NEW
        self._previous_state = chat_state.NEW
        self._city = None
        self._suggested_neighs = None
        self._suggested_cities = None
        self._suggested_airports = None

    def change_state(self, new_state):
        self._previous_state = self._state
        self._state = new_state

    def change_aux_state(self, new_aux_state):
        self._auxstate = new_aux_state

    def change_to_previous_state(self):
        self._state = self._previous_state

    def get_state(self):
        return self._state

    def get_aux_state(self):
        return self._auxstate

    def change_city(self, city):
        self._city = city

    def get_city(self):
        return self._city

    def set_suggested_neighs(self, neighs):
        self._suggested_neighs = neighs

    def get_suggested_neighs(self):
        return self._suggested_neighs

    def set_suggested_f_cities(self, cities):
        self._suggested_cities = cities

    def get_suggested_f_cities(self):
        return self._suggested_cities

    def set_sugg_airports(self, airports):
        self._suggested_airports = airports

    def get_sugg_airports(self):
        return self._suggested_airports

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
    def get_chat(self, chat_id):
        return self._chats[chat_id]

    def get_chats_ids(self):
        return self._chats.keys()

    # get chat state
    def get_chat_state(self, chat_id):
        return self._chats[chat_id].get_state()

    # get auxiliar chat state
    def get_chat_aux_state(self, chat_id):
        return self._chats[chat_id].get_aux_state()

    # NOT EFFICIENT
    def modify_state_from_chat(self, chat, new_state):
        for k,v in self._chats.iteritems():
            if v == chat:
                if new_state == "previous":
                    self._chats[k].change_to_previous_state()
                else:
                    self._chats[k].change_state(new_state)
                    break

    # EFFICIENT WAY TO CHANGE STATE
    def modify_state_from_id(self, chat_id, new_state):
        if new_state == "previous":
            self._chats[chat_id].change_to_previous_state()
        else:
            self._chats[chat_id].change_state(new_state)

    def modify_aux_state_from_id(self, chat_id, new_aux_state):
        self._chats[chat_id].change_aux_state(new_aux_state)

    def set_city_to_chat(self, chat_id, city):
        self._chats[chat_id].change_city(city)

    def get_city_from_chat(self, chat_id):
        return self._chats[chat_id].get_city()

    def set_suggested_neighs_to_chat(self, chat_id, neighs):
        self._chats[chat_id].set_suggested_neighs(neighs)

    def get_suggested_neighs_from_chat(self, chat_id):
        return self._chats[chat_id].get_suggested_neighs()

    def set_suggested_flight_cities(self, chat_id, cities):
        self._chats[chat_id].set_suggested_f_cities(cities)

    def get_suggested_flight_cities(self, chat_id):
        return self._chats[chat_id].get_suggested_f_cities()

    def set_suggested_airports(self, chat_id, airports):
        self._chats[chat_id].set_sugg_airports(airports)

    def get_suggested_airports(self, chat_id):
        return self._chats[chat_id].get_sugg_airports()

""" Class object to store the user preferences """
class FeatureFilter(object):

    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.features = {"cityInt":None, "cityName":None, "neighbourhood":None, "centrality":None, "price":None}

    def get_filter_features(self):
        return self.features

    def print_filters(self):
        return print_features(self.features)

    def assign_value(self, key, value):
        self.features[key] = value

    def reset_filters(self):
        self.features = {"cityInt":None, "cityName":None, "neighbourhood":None, "centrality":None, "price":None}

    def delete_data(self):
        self.chat_id = None
        self.features = {"cityInt":None, "cityName":None, "neighbourhood":None, "centrality":None, "price":None}


class FlightFilter(object):

    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.options = {"from":None,
                        "to":None,
                        "when":None}

    def get_flight_filters(self):
        return self.options

    def get_value_from_key(self, key):
        return self.options[key]

    def assign_value(self, key, value):
        if key in self.options.keys():
            self.options[key] = value

    def reset_filters(self):
        self.options = {"from":None,
                        "to":None,
                        "when":None}

    def delete_data(self):
        self.chat_id = None
        self.features = {"from":None,
                        "to":None,
                        "when":None}


####################################################################################

# Accept commands from owner.
class MessageHandler(telepot.helper.ChatHandler):

    def __init__(self, seed_tuple, chats, flight_predictor, **kwargs):
        super(MessageHandler, self).__init__(seed_tuple, **kwargs)
        self._db_retrieving = DatabaseRetrieving()
        self._chats = chats
        self._bot = self.bot
        self._reviews = MongoHandler(dbname="TravelChatbot_UserLogs", col_name="Reviews")
        self._msg_inline_keyboard = None
        self.first_option = None
        self.feature_filter = FeatureFilter(seed_tuple[2])
        self.flight_filter = FlightFilter(seed_tuple[2])
        self.recommender = HotelRecommender()
        self.analyser = None
        self.sentiment_results = None
        self.flight_predictor = flight_predictor

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

    def check_valid_date(self, msg):
        try:
            date = datetime.datetime.strptime(msg, '%Y-%m-%d').date()
            if date < datetime.datetime.today().date():
                return "wrong_date"
            else:
                return "ok"
        except ValueError:
            return "wrong_format"

    def convert_sent_results(self, results):
        return { "sentiment": results["sentiment"],
                 "confidence": results["confidence"],
                 "content": results["content"],
                 "topics": list(dict(results["topics"]))
                }


    # This method deals with text messages
    def on_chat_message(self, msg):
        content_type, chat_type, chat_id, msg_date, msg_id = telepot.glance(msg, long=True)

        if content_type != 'text':
            return

        com = msg['text'].lower()


        if chat_id not in self._chats.get_chats_ids():
            self._chats.put(chat_id)
            self._bot.sendMessage(chat_id, welcome_message(), parse_mode="Markdown")
            chat_not_new =  False

        city_chat = self._chats.get_city_from_chat(chat_id)

        # START QUESTION
        if self._chats.get_chat_state(chat_id) == chat_state.NEW:

            if com == command.START:

                # Ask whether the user wants to choose Flight - Hotel - Both
                self._chats.modify_state_from_id(chat_id, chat_state.FIRST_QUESTION)
                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="Flight", callback_data="only_flight")],
                             [InlineKeyboardButton(text="Hotel", callback_data="only_hotel")],
                             [InlineKeyboardButton(text="Both", callback_data="both")],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_first_question(), parse_mode="Markdown", reply_markup=markup)

        # FLIGHT DEPARTURE CITY QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.FLIGHT_FROM:

            if self._chats.get_chat_aux_state(chat_id) == auxiliar_state.FLIGHT_FROM_WRITE_NEW:

                nearest_cities = find_nearest(com, self.flight_predictor.get_airport_cities())
                self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.FLIGHT_FROM_WRITE_NOTNEW)
                self._chats.set_suggested_flight_cities(chat_id, nearest_cities)
                # show options as a list
                if isinstance(nearest_cities, str):
                    self._bot.sendMessage(chat_id, ask_write_flight_city(nearest_cities, False), parse_mode="Markdown")
                else:
                    self._bot.sendMessage(chat_id, ask_write_flight_city(nearest_cities, True), parse_mode="Markdown")

            elif self._chats.get_chat_aux_state(chat_id) == auxiliar_state.FLIGHT_FROM_WRITE_NOTNEW:

                if isinstance(self._chats.get_suggested_flight_cities(chat_id), str):

                    if com == "0":
                        n = self._chats.get_suggested_flight_cities(chat_id)
                        airports = self.flight_predictor.find_airports_from_city(n)

                        if len(airports) == 1:

                            self.flight_filter.assign_value("from", airports[0])
                            self._bot.sendMessage(chat_id, "Got it. Departure airport: *" + airports[0] + "*", parse_mode="Markdown")

                            # follow the process
                            self._chats.modify_state_from_id(chat_id, chat_state.FLIGHT_TO)
                            self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.FLIGHT_TO_WRITE_NEW)
                            self._bot.sendMessage(chat_id, ask_flight_to(), parse_mode="Markdown")

                        elif len(airports) > 1:

                            self._chats.set_suggested_airports(chat_id, airports)
                            # follow the process
                            self._chats.modify_state_from_id(chat_id, chat_state.FLIGHT_FROM_AIRPORT)
                            # Ask departure airport
                            self._bot.sendMessage(chat_id, choose_airport(airports), parse_mode="Markdown")

                    elif com == "1":

                        self._bot.sendMessage(chat_id, "Okay, write down again the departure city.", parse_mode="Markdown")
                        self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.FLIGHT_FROM_WRITE_NEW)

                    else:
                        self._bot.sendMessage(chat_id, "Wrong option", parse_mode="Markdown")

                else:

                    if com in [str(i) for i in range(len(self._chats.get_suggested_flight_cities(chat_id)))]:

                        idx = int(com)
                        nearest_c = self._chats.get_suggested_flight_cities(chat_id)
                        airports = self.flight_predictor.find_airports_from_city(nearest_c[idx])

                        if len(airports) == 1:
                            self.flight_filter.assign_value("from", airports[0])
                            self._bot.sendMessage(chat_id, "Got it. Departure airport: *" + airports[0] + "*", parse_mode="Markdown")

                            # follow the process
                            self._chats.modify_state_from_id(chat_id, chat_state.FLIGHT_TO)
                            self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.FLIGHT_TO_WRITE_NEW)
                            self._bot.sendMessage(chat_id, ask_flight_to(), parse_mode="Markdown")

                        elif len(airports) > 1:
                            self._chats.set_suggested_airports(chat_id, airports)
                            # follow the process
                            self._chats.modify_state_from_id(chat_id, chat_state.FLIGHT_FROM_AIRPORT)
                            # Ask departure airport
                            self._bot.sendMessage(chat_id, choose_airport(airports), parse_mode="Markdown")

                    # user chose None of them
                    elif com == str(len(self._chats.get_suggested_flight_cities(chat_id))):
                        self._bot.sendMessage(chat_id, "Okay, write down again the departure city.", parse_mode="Markdown")
                        self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.FLIGHT_FROM_WRITE_NEW)

                    else:
                        self._bot.sendMessage(chat_id, "Wrong option", parse_mode="Markdown")

        # FLIGHT DEPARTURE AIRPORT QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.FLIGHT_FROM_AIRPORT:

            if com in [str(i) for i in range(len(self._chats.get_suggested_airports(chat_id)))]:

                idx = int(com)
                airports = self._chats.get_suggested_airports(chat_id)
                self.flight_filter.assign_value("from", airports[idx])
                self._bot.sendMessage(chat_id, "Got it. Departure airport: *" + airports[idx] + "*", parse_mode="Markdown")

                # follow the process
                self._chats.modify_state_from_id(chat_id, chat_state.FLIGHT_TO)
                self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.FLIGHT_TO_WRITE_NEW)
                self._bot.sendMessage(chat_id, ask_flight_to(), parse_mode="Markdown")

            else:
                self._bot.sendMessage(chat_id, "Wrong option.")

        # DESTINATION CITY FLIGHT QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.FLIGHT_TO:

            if self._chats.get_chat_aux_state(chat_id) == auxiliar_state.FLIGHT_TO_WRITE_NEW:

                nearest_cities = find_nearest(com, self.flight_predictor.get_airport_cities())
                self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.FLIGHT_TO_WRITE_NOTNEW)
                self._chats.set_suggested_flight_cities(chat_id, nearest_cities)
                # show options as a list
                if isinstance(nearest_cities, str):
                    self._bot.sendMessage(chat_id, ask_write_flight_city(nearest_cities, False), parse_mode="Markdown")
                else:
                    self._bot.sendMessage(chat_id, ask_write_flight_city(nearest_cities, True), parse_mode="Markdown")

            elif self._chats.get_chat_aux_state(chat_id) == auxiliar_state.FLIGHT_TO_WRITE_NOTNEW:

                if isinstance(self._chats.get_suggested_flight_cities(chat_id), str):

                    if com == "0":
                        n = self._chats.get_suggested_flight_cities(chat_id)
                        airports = self.flight_predictor.find_airports_from_city(n)

                        if len(airports) == 1:
                            self.flight_filter.assign_value("to", "BCN") # TODO CHANGE WHEN SUPPORT OTHER CITIES THAN BCN
                            self._bot.sendMessage(chat_id, "Got it. Destination airport: *" + "BCN" + "*", parse_mode="Markdown")

                            # follow the process
                            self._bot.sendMessage(chat_id, ask_departure_date(), parse_mode="Markdown")
                            self._chats.modify_state_from_id(chat_id, chat_state.FLIGHT_WHEN)

                        elif len(airports) > 1:
                            self._chats.set_suggested_airports(chat_id, airports)
                            # follow the process
                            self._chats.modify_state_from_id(chat_id, chat_state.FLIGHT_TO_AIRPORT)
                            # Ask departure airport
                            self._bot.sendMessage(chat_id, choose_airport(airports), parse_mode="Markdown")

                    elif com == "1":
                        self._bot.sendMessage(chat_id, "Okay, write down again the destination city.", parse_mode="Markdown")
                        self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.FLIGHT_TO_WRITE_NEW)

                    else:
                        self._bot.sendMessage(chat_id, "Wrong option", parse_mode="Markdown")

                else:
                    if com in [str(i) for i in range(len(self._chats.get_suggested_flight_cities(chat_id)))]:
                        idx = int(com)
                        nearest_c = self._chats.get_suggested_flight_cities(chat_id)
                        airports = self.flight_predictor.find_airports_from_city(nearest_c[idx])

                        if len(airports) == 1:
                            self.flight_filter.assign_value("to", "BCN") # TODO CHANGE WHEN SUPPORT OTHER CITIES THAN BCN
                            self._bot.sendMessage(chat_id, "Got it. Destination airport: *BCN*", parse_mode="Markdown")

                            # follow the process
                            self._bot.sendMessage(chat_id, ask_departure_date(), parse_mode="Markdown")
                            self._chats.modify_state_from_id(chat_id, chat_state.FLIGHT_WHEN)

                        elif len(airports) > 1:
                            self._chats.set_suggested_airports(chat_id, airports)
                            # follow the process
                            self._chats.modify_state_from_id(chat_id, chat_state.FLIGHT_TO_AIRPORT)
                            # Ask departure airport
                            self._bot.sendMessage(chat_id, choose_airport(airports), parse_mode="Markdown")

                    # user chose None of them
                    elif com == str(len(self._chats.get_suggested_flight_cities(chat_id))):
                        self._bot.sendMessage(chat_id, "Okay, write down again the destination city.", parse_mode="Markdown")
                        self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.FLIGHT_TO_WRITE_NEW)

                    else:
                        self._bot.sendMessage(chat_id, "Wrong option", parse_mode="Markdown")

        # FLIGHT DESTINATION AIRPORT QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.FLIGHT_TO_AIRPORT:

            if com in [str(i) for i in range(len(self._chats.get_suggested_airports(chat_id)))]:
                idx = int(com)
                airports = self._chats.get_suggested_airports(chat_id)
                self.flight_filter.assign_value("to", "BCN") # TODO CHANGE WHEN SUPPORT OTHER CITIES THAN BCN
                self._bot.sendMessage(chat_id, "Got it. Destination airport: *BCN*", parse_mode="Markdown")

                # follow the process
                self._bot.sendMessage(chat_id, ask_departure_date(), parse_mode="Markdown")
                self._chats.modify_state_from_id(chat_id, chat_state.FLIGHT_WHEN)
            else:
                self._bot.sendMessage(chat_id, "Wrong option.")

        # DEPARTURE DATE QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.FLIGHT_WHEN:

            result = self.check_valid_date(com)
            if result == "ok":

                self.flight_filter.assign_value("when", com)
                self._bot.sendMessage(chat_id, "Got it. Departure date: *" + com + "*", parse_mode="Markdown")

                # follow the process
                rec = self.flight_predictor.find_best_flight(self.flight_filter.get_flight_filters())
                # rec = ('2017-07-13', 131.81630000000001, from, 'BCN')

                self._bot.sendMessage(chat_id, rec_flight(rec, self.flight_predictor.get_airport_dict()), parse_mode="Markdown")

                # follow the process
                if self.first_option == "only_flight":

                    self._chats.modify_state_from_id(chat_id, chat_state.FLIGHT_ONLY_FINISHED)
                    self._bot.sendMessage(chat_id, ask_to_follow_to_hotel(), parse_mode="Markdown")
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="Yes", callback_data="yes_follow_to_hotel"), InlineKeyboardButton(text="No", callback_data="no_follow_to_hotel")],
                             ])
                    city_name = self.flight_predictor.get_city_from_airport(self.flight_filter.get_value_from_key("to"))
                    self._msg_inline_keyboard = self._bot.sendMessage(chat_id, "Would you like to get an hotel recommendation in %s?" % city_name, parse_mode="Markdown", reply_markup=markup)

                elif self.first_option == "both":

                    city = self.flight_predictor.get_city_from_airport(self.flight_filter.get_value_from_key("to"))
                    city = "Barcelona"

                    num_hotels = self._db_retrieving.find_number_hotels_by_cities()

                    # RECOMMENDATION FILTER HERE
                    self.feature_filter.assign_value("cityInt", self._db_retrieving.city2int(city))
                    self.feature_filter.assign_value("cityName", city)

                    self._bot.sendMessage(chat_id, "Nice, I finished with the flight recommendation.\n\nI proceed to recommend you hotels in *%s* (%d hotels)." % (city, num_hotels[city]), parse_mode="Markdown")
                    self._chats.set_city_to_chat(chat_id, city)

                    # follow the process
                    self._chats.modify_state_from_id(chat_id, chat_state.NEIGHBOURHOOD)
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="Yes", callback_data="yes_neigh"), InlineKeyboardButton(text="No", callback_data="no_neigh")],
                             ])
                    self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_neighbourhood_1(), parse_mode="Markdown", reply_markup=markup)

            elif result == "wrong_format":
                self._bot.sendMessage(chat_id, wrong_departure_date_format(), parse_mode="Markdown")
            elif result == "wrong_date":
                self._bot.sendMessage(chat_id, not_valid_date(), parse_mode="Markdown")

        # NEIGHBOURHOOD LIST QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.NEIGHBOURHOOD_YES_LIST:

            if com in self._db_retrieving.get_neighbourhoods_answers_from_city(city_chat):

                # RECOMMENDATION FILTER
                chosen_neigh = self._db_retrieving.get_neighbourhood_from_index(city_chat, int(com))
                self.feature_filter.assign_value("neighbourhood",chosen_neigh)

                # show feedback to user
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "I've got the neighbourhood: *%s*" % chosen_neigh , parse_mode="Markdown")
                self._bot.sendMessage(chat_id, "Okay! I've got the neighbourhood: *%s*" % chosen_neigh, parse_mode="Markdown")

                # follow the process
                self._chats.modify_state_from_id(chat_id, chat_state.PRICE)
                self._bot.sendMessage(chat_id,
                                        price_range_stats(self._db_retrieving.get_prices_from_features(self.feature_filter.get_filter_features())), parse_mode="Markdown")
                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="Yes", callback_data="yes_price"), InlineKeyboardButton(text="No", callback_data="no_price")],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_if_price_range(), parse_mode="Markdown", reply_markup=markup)

            else:
                self._bot.sendMessage(chat_id, "Ouch, you chose a wrong option. Please try again.", parse_mode="Markdown")

        # NEIGHBOURHOOD WRITE QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.NEIGHBOURHOOD_YES_WRITE:

            # IF FIRST TIME TYPING A NEIGHBOURHOOD
            if self._chats.get_chat_aux_state(chat_id) == auxiliar_state.NEIGH_WRITE_NEW:
                nearest_neighs = find_nearest(com, self._db_retrieving.get_neighbourhoods_from_city(city_chat))
                self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.NEIGH_WRITE_NOTNEW)
                self._chats.set_suggested_neighs_to_chat(chat_id, nearest_neighs)
                # show options as a list
                if isinstance(nearest_neighs, str):
                    num_hotels = self._db_retrieving.find_number_hotels_by_neigh(1, nearest_neighs)
                    self._bot.sendMessage(chat_id, ask_write_neighbourhood2(nearest_neighs, num_hotels, False), parse_mode="Markdown")
                else:
                    num_hotels = self._db_retrieving.find_number_hotels_by_neigh(3, nearest_neighs)
                    self._bot.sendMessage(chat_id, ask_write_neighbourhood2(nearest_neighs,num_hotels, True), parse_mode="Markdown")

            # IF NOT FIRST
            elif self._chats.get_chat_aux_state(chat_id) == auxiliar_state.NEIGH_WRITE_NOTNEW:

                # User chose one of suggested neighbourhood options
                if isinstance(self._chats.get_suggested_neighs_from_chat(chat_id), str):
                    if com == "0":
                        n = self._chats.get_suggested_neighs_from_chat(chat_id)
                        self.feature_filter.assign_value("neighbourhood", n)
                        self._bot.sendMessage(chat_id, "Got it. I stored the neighbourhood: " + n, parse_mode="Markdown")

                        # follow the process
                        self._chats.modify_state_from_id(chat_id, chat_state.PRICE)
                        self._bot.sendMessage(chat_id,
                                                price_range_stats(self._db_retrieving.get_prices_from_features(self.feature_filter.get_filter_features())), parse_mode="Markdown")

                        markup = InlineKeyboardMarkup(inline_keyboard=[
                                     [InlineKeyboardButton(text="Yes", callback_data="yes_price"), InlineKeyboardButton(text="No", callback_data="no_price")],
                                 ])
                        self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_if_price_range(), parse_mode="Markdown", reply_markup=markup)

                    elif com == "1":
                        self._bot.sendMessage(chat_id, ask_write_neighbourhood_again(), parse_mode="Markdown")
                        self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.NEIGH_WRITE_NEW)

                else:
                    if com in [str(i) for i in range(len(self._chats.get_suggested_neighs_from_chat(chat_id)))]:
                        idx = int(com)
                        nearest_n = self._chats.get_suggested_neighs_from_chat(chat_id)
                        self.feature_filter.assign_value("neighbourhood", nearest_n[idx])
                        self._bot.sendMessage(chat_id, "Got it. I stored the neighbourhood: " + nearest_n[idx], parse_mode="Markdown")

                        # follow the process
                        self._chats.modify_state_from_id(chat_id, chat_state.PRICE)
                        self._bot.sendMessage(chat_id,
                                                price_range_stats(self._db_retrieving.get_prices_from_features(self.feature_filter.get_filter_features())), parse_mode="Markdown")

                        markup = InlineKeyboardMarkup(inline_keyboard=[
                                     [InlineKeyboardButton(text="Yes", callback_data="yes_price"), InlineKeyboardButton(text="No", callback_data="no_price")],
                                 ])
                        self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_if_price_range(), parse_mode="Markdown", reply_markup=markup)

                    # user chose None of them
                    elif com == str(len(self._chats.get_suggested_neighs_from_chat(chat_id))):
                        self._bot.sendMessage(chat_id, ask_write_neighbourhood_again(), parse_mode="Markdown")
                        self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.NEIGH_WRITE_NEW)


        # PRICE QUESTION
        if self._chats.get_chat_state(chat_id) == chat_state.PRICE_YES:

            if self.is_price_range(com):

                self._bot.sendMessage(chat_id, "Okay, correct price format!", parse_mode="Markdown")
                self._chats.modify_state_from_id(chat_id, chat_state.CONFIRMING)

                # RECOMMENDATION FILTER
                self.feature_filter.assign_value("price", self.parse_price_range(com))

                # FOLLOW PROCESS HERE
                self._bot.sendMessage(chat_id, self.feature_filter.print_filters(), parse_mode="Markdown")
                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="OK", callback_data="no_change"), InlineKeyboardButton(text="Change", callback_data="yes_change")],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, "Are they OK?", parse_mode="Markdown", reply_markup=markup)

            else:
                self._bot.sendMessage(chat_id, price_format_wrong(), parse_mode="Markdown")

        # SENTIMENT ANALYSER QUESTION
        if self._chats.get_chat_state(chat_id) == chat_state.REVIEW_USER:

            _, results = self.analyser.analyse(com)
            self.sentiment_results = results
            # send message to user explaining results
            self._bot.sendMessage(chat_id, explain_sentiment_results(results), parse_mode="Markdown")
            markup = InlineKeyboardMarkup(inline_keyboard=[
                         [InlineKeyboardButton(text="OK", callback_data="sent_no_change"), InlineKeyboardButton(text="Change", callback_data="sent_yes_change")],
                     ])
            self._msg_inline_keyboard = self._bot.sendMessage(chat_id, "Are the results OK with you?", parse_mode="Markdown", reply_markup=markup)

        # QUIT MODE
        if self._chats.get_chat_state(chat_id) != chat_state.QUITTING:

            if com == command.QUIT:

                self._chats.modify_state_from_id(chat_id, chat_state.QUITTING)

                if int(self._chats.get_chat_state(chat_id)) < 3:
                    self._bot.sendMessage(chat_id, "I can't do this option because you just started the process.\
                                                    \nIf you don't want to interact with me just ignore me, I will be here anytime.", parse_mode="Markdown")
                else:
                    # show feedback to user
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="Yes", callback_data="yes_quit"), InlineKeyboardButton(text="No", callback_data="no_quit")],
                             ])
                    self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_quit(), parse_mode="Markdown", reply_markup=markup)

        # REPEAT THE WHOLE PROCESS
        if self._chats.get_chat_state(chat_id) != chat_state.REPEATING:

            if com == command.REPEAT:

                self._chats.modify_state_from_id(chat_id, chat_state.REPEATING)

                # show feedback to user
                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="Yes", callback_data="yes_repeat"), InlineKeyboardButton(text="No", callback_data="no_repeat")],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_repeat(), parse_mode="Markdown", reply_markup=markup)

    # This method deals with callback messages
    def on_callback_query(self, msg):
        query_id, chat_id, data = telepot.glance(msg, flavor='callback_query', long=True)

        if int(self._chats.get_chat_state(chat_id)) > 4:
            city = self._chats.get_city_from_chat(chat_id)

        # FIRST QUESTION
        if self._chats.get_chat_state(chat_id) == chat_state.FIRST_QUESTION:

            if data == "only_flight":
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Okay! You have chosen the option: *FLIGHT*", parse_mode="Markdown")
                self.first_option = data

                # Ask departure airport
                self._chats.modify_state_from_id(chat_id, chat_state.FLIGHT_FROM)
                self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.FLIGHT_FROM_WRITE_NEW)
                self._bot.sendMessage(chat_id, ask_flight_from(), parse_mode="Markdown")

            elif data == "only_hotel":

                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Okay! You have chosen the option: *HOTEL*", parse_mode="Markdown")
                self.first_option = data

                # HOTEL CITY
                self._chats.modify_state_from_id(chat_id, chat_state.CITY)
                num_hotels = self._db_retrieving.find_number_hotels_by_cities()
                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text=city + " (%d hotels)" % num_hotels[city], callback_data=city) for city in self._db_retrieving.get_cities()],
                         ])
                self._bot.sendMessage(chat_id, hotel_rec_starter(), parse_mode="Markdown")
                self._msg_inline_keyboard = bot.sendMessage(chat_id, ask_city_question(), parse_mode="Markdown",reply_markup=markup)

            elif data == "both":

                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Okay! You have chosen the option: *FLIGHT AND HOTEL*", parse_mode="Markdown")
                self.first_option = data
                # Ask departure airport
                self._chats.modify_state_from_id(chat_id, chat_state.FLIGHT_FROM)
                self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.FLIGHT_FROM_WRITE_NEW)
                self._bot.sendMessage(chat_id, ask_flight_from(), parse_mode="Markdown")

        elif self._chats.get_chat_state(chat_id) == chat_state.FLIGHT_ONLY_FINISHED:

            if data == "yes_follow_to_hotel":
                # show feedback to user
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Superb! Thank you.", parse_mode="Markdown")

                city = self.flight_predictor.get_city_from_airport(self.flight_filter.get_value_from_key("to"))
                city = "Barcelona"

                num_hotels = self._db_retrieving.find_number_hotels_by_cities()
                # RECOMMENDATION FILTER HERE
                self.feature_filter.assign_value("cityInt", self._db_retrieving.city2int(city))
                self.feature_filter.assign_value("cityName", city)

                self._bot.sendMessage(chat_id, "I proceed to recommend you hotels in *%s* (%d hotels)." % (city, num_hotels[city]), parse_mode="Markdown")
                self._chats.set_city_to_chat(chat_id, city)

                # follow the process
                self._chats.modify_state_from_id(chat_id, chat_state.NEIGHBOURHOOD)
                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="Yes", callback_data="yes_neigh"), InlineKeyboardButton(text="No", callback_data="no_neigh")],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_neighbourhood_1(), parse_mode="Markdown", reply_markup=markup)

            elif data == "no_follow_to_hotel":
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "No problem, thank you for using my services!\n\nRemember that if you want to use me again just type */repeat*.", parse_mode="Markdown")


        # CITY QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.CITY:

            if data in self._db_retrieving.get_cities():

                # RECOMMENDATION FILTER HERE
                self.feature_filter.assign_value("cityInt", self._db_retrieving.city2int(data))
                self.feature_filter.assign_value("cityName", data)

                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Got it, City: *%s*" % data, parse_mode="Markdown")
                self._chats.set_city_to_chat(chat_id,data)

                # follow the process
                self._chats.modify_state_from_id(chat_id, chat_state.NEIGHBOURHOOD)
                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="Yes", callback_data="yes_neigh"), InlineKeyboardButton(text="No", callback_data="no_neigh")],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_neighbourhood_1(), parse_mode="Markdown", reply_markup=markup)

        # # ROOM QUESTION
        # elif self._chats.get_chat_state(chat_id) == chat_state.ROOM:
        #
        #     if data == "Individual" or data == "Double" or data == "More":
        #
        #         # RECOMMENDATION FILTER HERE
        #         self.feature_filter.assign_value("room",data)
        #
        #         msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
        #         self._bot.editMessageText(msg_idf, "Got it, Room type: *%s*" % data, parse_mode="Markdown")
        #
        #         # follow the process
        #         self._chats.modify_state_from_id(chat_id, chat_state.NEIGHBOURHOOD)
        #         markup = InlineKeyboardMarkup(inline_keyboard=[
        #                      [InlineKeyboardButton(text="Yes", callback_data="yes_neigh"), InlineKeyboardButton(text="No", callback_data="no_neigh")],
        #                  ])
        #         self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_neighbourhood_1(), parse_mode="Markdown", reply_markup=markup)

        # NEIGHBOURHOOD QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.NEIGHBOURHOOD:

            if data == "yes_neigh":
                # show feedback to user
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Okay.", parse_mode="Markdown")
                # follow the process
                self._chats.modify_state_from_id(chat_id, chat_state.NEIGHBOURHOOD_YES)

                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="Choose from list", callback_data="list_neigh"), InlineKeyboardButton(text="Write it down", callback_data="write_neigh")],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_mode_neighbourhood(), parse_mode="Markdown", reply_markup=markup)


            elif data == "no_neigh":
                # show feedback to user
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "No problem.")

                # follow the process
                num_hotels = self._db_retrieving.find_number_hotels_by_centrality()
                self._chats.modify_state_from_id(chat_id, chat_state.CENTRALITY)
                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text=options_central[0] + " (%d hotels)" % num_hotels[options_central[0]], callback_data=options_central[0]), InlineKeyboardButton(text=options_central[1] + " (%d hotels)" % num_hotels[options_central[1]], callback_data=options_central[1])],
                             [InlineKeyboardButton(text=options_central[2] + " (%d hotels)" % num_hotels[options_central[2]], callback_data=options_central[2]), InlineKeyboardButton(text=options_central[3], callback_data=options_central[3])],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_central(), parse_mode="Markdown", reply_markup=markup)

        # NEIGHBOURHOOD_YES QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.NEIGHBOURHOOD_YES:

            if data == "list_neigh":
                # show feedback to user
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Okay.", parse_mode="Markdown")
                # follow the process
                self._chats.modify_state_from_id(chat_id, chat_state.NEIGHBOURHOOD_YES_LIST)
                # show neighbourhoods as a list
                neighs = self._db_retrieving.get_neighbourhoods_from_city(city)
                num_hotels = self._db_retrieving.find_number_hotels_by_neigh(5)
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_neighbourhood_2(neighs, num_hotels), parse_mode="Markdown")

            elif data == "write_neigh":
                # show feedback to user
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Okay.", parse_mode="Markdown")
                # follow the process
                self._chats.modify_state_from_id(chat_id, chat_state.NEIGHBOURHOOD_YES_WRITE)
                self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.NEIGH_WRITE_NEW)
                self._bot.sendMessage(chat_id, ask_write_neighbourhood(), parse_mode="Markdown")

        # CENTRALITY QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.CENTRALITY:

            if data in options_central:

                # show feedback to user
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Got it, Centrality: *%s*" % data , parse_mode="Markdown")

                self.feature_filter.assign_value("centrality", data if data in options_central[:-1] else None)

                # follow the process
                self._chats.modify_state_from_id(chat_id, chat_state.PRICE)
                self._bot.sendMessage(chat_id,
                                        price_range_stats(self._db_retrieving.get_prices_from_features(self.feature_filter.get_filter_features())), parse_mode="Markdown")
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
                    self._bot.sendMessage(chat_id, self.feature_filter.print_filters(), parse_mode="Markdown")
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="OK", callback_data="no_change"), InlineKeyboardButton(text="Change", callback_data="yes_change")],
                             ])
                    self._msg_inline_keyboard = self._bot.sendMessage(chat_id, "Are they OK?", parse_mode="Markdown", reply_markup=markup)


        # CHANGE FILTERING QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.CONFIRMING:

            if data == "yes_change" or data == "no_change":

                if data == "yes_change":

                    # reset whole process and ask first question (city) again
                    msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                    self._bot.sendMessage(chat_id, "Okay, now you will be asked all the questions again.\n", parse_mode="Markdown")

                    self.feature_filter.reset_filters()

                    self._chats.modify_state_from_id(chat_id, chat_state.CITY)
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text=city, callback_data=city) for city in self._db_retrieving.get_cities() ],
                             ])
                    self._bot.sendMessage(chat_id, hotel_rec_starter(), parse_mode="Markdown")
                    self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_city_question(), parse_mode="Markdown",reply_markup=markup)

                else:
                    # RECOMMEND HOTEL HERE
                    msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                    self._bot.editMessageText(msg_idf, "Great! Please, wait until I process your personalized hotel recommendations...")
                    self._chats.modify_state_from_id(chat_id, chat_state.RECOMMENDATION)

                    self.recommender.set_features(self.feature_filter.get_filter_features())
                    success, n_preds = self.recommender.fit()
                    if success:
                        predictions = self.recommender.show_n_predictions(5)

                        for pred in predictions:
                            self._bot.sendMessage(chat_id, pred, parse_mode="Markdown")


                        if n_preds <= 5:
                            markup = InlineKeyboardMarkup(inline_keyboard=[
                                         [InlineKeyboardButton(text="Done", callback_data="done_rec")],
                                     ])
                            self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_recommendation_followup2(), parse_mode="Markdown",reply_markup=markup)

                        else:
                            markup = InlineKeyboardMarkup(inline_keyboard=[
                                         [InlineKeyboardButton(text="Done", callback_data="done_rec"), InlineKeyboardButton(text="Show more", callback_data="show_more_rec")],
                                     ])
                            self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_recommendation_followup(), parse_mode="Markdown",reply_markup=markup)

                    else:
                        self._bot.sendMessage(chat_id, "I am so sorry, I did not find any hotels matching your preferences in my database...", parse_mode="Markdown")

        # AFTER RECOMMENDATION QUESTION
        elif self._chats.get_chat_state(chat_id) == chat_state.RECOMMENDATION :

            if data == "done_rec":
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, ask_review_user(), parse_mode="Markdown")

                # change state to SentimentAnalyser
                self._chats.modify_state_from_id(chat_id, chat_state.REVIEW_USER)
                # instance sentiment analyser
                clf, vectorizer = model.load_model_and_vectorizer()
                self.analyser = SentimentAnalyser(clf, vectorizer, "topic_criteria/criteria.txt")

            elif data == "show_more_rec":
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Okay. Showing next 1-5 recommendations:")

                predictions = self.recommender.show_n_predictions(5, show_next=5)

                for pred in predictions:
                    self._bot.sendMessage(chat_id, pred, parse_mode="Markdown")

                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="Done", callback_data="done_rec")],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_recommendation_followup2(), parse_mode="Markdown",reply_markup=markup)

        # SENTIMENT ANALYSIS CONFIRMATION
        elif self._chats.get_chat_state(chat_id) == chat_state.REVIEW_USER:

            if data == "sent_no_change":
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, sent_analysis_confirmation(), parse_mode="Markdown")

                results_to_mongo = self.convert_sent_results(self.sentiment_results)
                results_to_mongo["chat_id"] = chat_id
                results_to_mongo["user_id"] = msg["from"]["id"]
                self._reviews.insert(results_to_mongo)

                # following process
                self._chats.modify_aux_state_from_id(chat_id, auxiliar_state.FINISHED)
                self._chats.modify_state_from_id(chat_id, chat_state.NEW)
                # reset data from filters
                self.flight_filter.reset_filters()
                self.feature_filter.reset_filters()

            elif data == "sent_yes_change":
                self.sentiment_results = None
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, ask_review_user2(), parse_mode="Markdown")


        # QUIT THE PROCESS
        if data == u"yes_quit" or data == u"no_quit":

            if data == u"yes_quit":
                # delete all data from filter
                self.feature_filter.delete_data()
                # delete chat
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "...", parse_mode="Markdown")
                self._chats.modify_state_from_id(chat_id, chat_state.NEW)

                self._chats.drop_from_id(chat_id)
                # delete all data from filters
                self.flight_filter.reset_filters()
                self.feature_filter.reset_filters()

                self._bot.sendMessage(chat_id, bye_message(), parse_mode="Markdown")

            else:
                self._chats.modify_state_from_id(chat_id, "previous")
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Thank you for keep trusting in me!\nPlease, now you should continue from the last question asked.", parse_mode="Markdown")

        # REPEAT THE PROCESS
        if data == u"yes_repeat" or data == u"no_repeat":

            if data == u"yes_repeat":
                # delete chat
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "...", parse_mode="Markdown")
                # delete all data from filters
                self.flight_filter.reset_filters()
                self.feature_filter.reset_filters()
                # put chat state to CITY
                self._chats.modify_state_from_id(chat_id, chat_state.NEW)
                # Ask whether the user wants to choose Flight - Hotel - Both
                self._chats.modify_state_from_id(chat_id, chat_state.FIRST_QUESTION)
                markup = InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="Flight", callback_data="only_flight")],
                             [InlineKeyboardButton(text="Hotel", callback_data="only_hotel")],
                             [InlineKeyboardButton(text="Both", callback_data="both")],
                         ])
                self._msg_inline_keyboard = self._bot.sendMessage(chat_id, ask_first_question(), parse_mode="Markdown", reply_markup=markup)

            else:
                self._chats.modify_state_from_id(chat_id, "previous")
                msg_idf = telepot.message_identifier(self._msg_inline_keyboard)
                self._bot.editMessageText(msg_idf, "Thank you for keep trusting in me!\nPlease, now you should continue from the last question asked.", parse_mode="Markdown")


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


class TravelChatbot(telepot.DelegatorBot):

    def __init__(self, token):

        self._chats = ChatCollection()
        self._flight_predictor = FlightPredictor("../../predict_flights/Rfregressor.pickle", "DCOILBRENTEU.csv")

        super(TravelChatbot, self).__init__(token, [
            # Here is a delegate to specially handle owner commands.
            include_callback_query_chat_id(
                pave_event_space())(
                    per_chat_id(), create_open, MessageHandler, self._chats, self._flight_predictor, timeout = 10e20),

            (per_application(), create_open(LogSaver, self._chats)),

        ])


if __name__=="__main__":

    TOKEN = "447957418:AAGypRqT_hq0q70D4LZPFvEa90b0BvRGhW4" # username: @travel_chatbot

    bot = TravelChatbot(TOKEN)

    # if updates, clear them
    updates = bot.getUpdates()

    if updates:
        last_update_id = updates[-1]['update_id']
        bot.getUpdates(offset=last_update_id+1)

    bot.message_loop(run_forever='Listening ...')
