#coding: utf-8

import sys
import time
import telepot.helper
import pickle
import pandas as pd
import numpy as np

from message_handler_bot import *

from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, ForceReply

DATABASE_FILE = "TFM---Travel-chat-bot/trivago_data/pandas_dbs/dataset.pkl"
db = pd.read_pickle(DATABASE_FILE)

prices = db.price.astype(np.float64)

message_with_inline_keyboard = None     # global variable to handle messages when inline keyboard enabled
started_greeting = False
started_mode = False                    # global variable to help handle bot logic
in_neigh_question = False
in_price_question = False
cities = ["Barcelona"]                  # retrieve cities from DATABASE #TODO
neighbourhoods = ["A","B","C","D"]      # retrieve neighbourhoods from DATABASE #TODO

greetings = ["hi","hola","hello","hey","uep"]
options_central = ["Much","Not much","Outskirts","Don't care"]
options_touristic = ["Yes", "Not really", "Don't care"]

numbers = [str(i) for i in range(len(neighbourhoods))]


def ask_location_central(bot, chat_id):

    markup = InlineKeyboardMarkup(inline_keyboard=[
                 [InlineKeyboardButton(text=options_central[0], callback_data=options_central[0]), InlineKeyboardButton(text=options_central[1], callback_data=options_central[1])],
                 [InlineKeyboardButton(text=options_central[2], callback_data=options_central[2]), InlineKeyboardButton(text=options_central[3], callback_data=options_central[3])],
             ])
    return bot.sendMessage(chat_id, ask_central(), parse_mode="Markdown", reply_markup=markup)

def ask_location_touristic(bot, chat_id):
    markup = InlineKeyboardMarkup(inline_keyboard=[
                 [InlineKeyboardButton(text=options_touristic[0], callback_data=options_touristic[0]),
                  InlineKeyboardButton(text=options_touristic[1], callback_data=options_touristic[1]),
                  InlineKeyboardButton(text=options_touristic[2], callback_data=options_touristic[2])],
             ])
    return bot.sendMessage(chat_id, ask_touristic(), parse_mode="Markdown", reply_markup=markup)

def ask_price_range(bot, chat_id):
    bot.sendMessage(chat_id, price_range_stats(prices), parse_mode="Markdown")

    markup = InlineKeyboardMarkup(inline_keyboard=[
                 [InlineKeyboardButton(text="Yes", callback_data="yes_price"), InlineKeyboardButton(text="No", callback_data="no_price")],
             ])

    return bot.sendMessage(chat_id, ask_if_price_range(), parse_mode="Markdown", reply_markup=markup)

def is_price_range(msg):
    try:
        values = msg.split(" ")
        if int(values[0]) and int(values[1]):
            return True
    except Exception:
        return False

# this will handle ALL text messages
def on_chat_message(msg):
    content_type, chat_type, chat_id = telepot.glance(msg)
    print('Chat:', content_type, chat_type, chat_id)

    global started_greeting
    global started_mode
    global in_price_question
    global in_neigh_question

    numbers = [str(i) for i in range(len(neighbourhoods))]

    if content_type != 'text':
        return

    command = msg['text'].lower()

    if in_price_question:
        if is_price_range(command):
            bot.sendMessage(chat_id, "Okay, correct price format!", parse_mode="Markdown")
            in_price_question = False
            # do something here with database
            #TODO

            # RECOMMEND HOTEL HERE or FOLLOW PROCESS HERE
            #TODO

        else:
            bot.sendMessage(chat_id, price_format_wrong(), parse_mode="Markdown")

    elif command in greetings:
        if not started_greeting:
            started_greeting = True
            bot.sendMessage(chat_id, welcome_message(), parse_mode="Markdown")
        else:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                         [InlineKeyboardButton(text="Yes", callback_data="start_over"), InlineKeyboardButton(text="No", callback_data="no_start_over")],
                     ])
            bot.sendMessage(chat_id, ask_reset(), parse_mode="Markdown", reply_markup=markup)

    elif command == "start":
        if not started_mode:
            started_mode = True
            markup = InlineKeyboardMarkup(inline_keyboard=[
                         [InlineKeyboardButton(text=city, callback_data=city) for city in cities],
                     ])

            bot.sendMessage(chat_id, hotel_rec_starter(), parse_mode="Markdown")
            global message_with_inline_keyboard
            message_with_inline_keyboard = bot.sendMessage(chat_id, ask_city_question(), parse_mode="Markdown",reply_markup=markup)
        else:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                         [InlineKeyboardButton(text="Yes", callback_data="start_over"), InlineKeyboardButton(text="No", callback_data="no_start_over")],
                     ])
            bot.sendMessage(chat_id, ask_reset(), parse_mode="Markdown", reply_markup=markup)

    elif in_neigh_question:

        if command in numbers:
            # do something with database here
            #TODO neighbourhoods[numbers.index(command)] # this should get you the neighbourhood

            # show feedback to user
            bot.sendMessage(chat_id, "Got it, Neighbourhood: *%s*" % neighbourhoods[numbers.index(command)], parse_mode="Markdown")
            in_neigh_question = False
            # follow the process
            message_with_inline_keyboard = ask_location_central(bot, chat_id)
        else:
            bot.sendMessage(chat_id, "Ouch, you chose a wrong option. Please try again.", parse_mode="Markdown")

    # quit
    elif command == "q":
        markup = ReplyKeyboardRemove()
        bot.sendMessage(chat_id, bye_message(), parse_mode="Markdown", reply_markup=markup)


# this will handle ALL callback queries
def on_callback_query(msg):
    query_id, from_id, data = telepot.glance(msg, flavor='callback_query')
    print('Callback query:', query_id, from_id, data)

    global message_with_inline_keyboard

    if data in cities:
        # do something with database here
        #TODO
        # show feedback to user
        msg_idf = telepot.message_identifier(message_with_inline_keyboard)
        bot.editMessageText(msg_idf, "Got it, City: *%s*" % data, parse_mode="Markdown")

        # follow the process
        markup = InlineKeyboardMarkup(inline_keyboard=[
                     [InlineKeyboardButton(text="Individual", callback_data="Individual"), InlineKeyboardButton(text="Double", callback_data="Double")],
                 ])
        message_with_inline_keyboard = bot.sendMessage(from_id, ask_roomtype_question(), parse_mode="Markdown", reply_markup=markup)

    elif data == "Individual" or data == "Double":
        # do something with database here
        #TODO
        # show feedback to user
        msg_idf = telepot.message_identifier(message_with_inline_keyboard)
        bot.editMessageText(msg_idf, "Got it, RoomType: *%s*" % data, parse_mode="Markdown")

        # follow the process
        markup = InlineKeyboardMarkup(inline_keyboard=[
                     [InlineKeyboardButton(text="Yes", callback_data="yes_neigh"), InlineKeyboardButton(text="No", callback_data="no_neigh")],
                 ])
        message_with_inline_keyboard = bot.sendMessage(from_id, ask_neighbourhood_1(), parse_mode="Markdown", reply_markup=markup)

    elif data == "yes_neigh" or data == "no_neigh":
        if data == "yes_neigh":
            # show feedback to user
            msg_idf = telepot.message_identifier(message_with_inline_keyboard)
            bot.editMessageText(msg_idf, "Okay.")
            # follow the process
            global in_neigh_question
            message_with_inline_keyboard = bot.sendMessage(from_id, ask_neighbourhood_2(neighbourhoods),parse_mode="Markdown")
            in_neigh_question = True
        elif data == "no_neigh":
            # show feedback to user
            msg_idf = telepot.message_identifier(message_with_inline_keyboard)
            bot.editMessageText(msg_idf, "No problem.")
            # follow the process
            message_with_inline_keyboard = ask_location_central(bot, from_id)

    elif data in options_central:
        idx = options_central.index(data)
        # show feedback to user
        msg_idf = telepot.message_identifier(message_with_inline_keyboard)
        bot.editMessageText(msg_idf, "Got it, Centrality: *%s*" % data , parse_mode="Markdown")

        # handle different types of centrality
        if idx == 0: # central: Much
            # do something here with database
            #TODO
            bot.sendMessage(from_id, notify_user_wait(),parse_mode="Markdown")
        elif idx == 1: # central: Not Much
            # do something here with database
            #TODO
            bot.sendMessage(from_id, notify_user_wait(),parse_mode="Markdown")
        elif idx == 2: # central: Outskirts
            # do something here with database
            #TODO
            bot.sendMessage(from_id, notify_user_wait(),parse_mode="Markdown")
        elif idx == 3: # centra: Don't care
            # do something here with database
            #TODO
            bot.sendMessage(from_id, notify_user_wait(),parse_mode="Markdown")

        # follow the process
        message_with_inline_keyboard = ask_location_touristic(bot, from_id)

    elif data in options_touristic:
        idx = options_touristic.index(data)
        # show feedback to user
        msg_idf = telepot.message_identifier(message_with_inline_keyboard)
        bot.editMessageText(msg_idf, "Got it, Touristic: *%s*" % data , parse_mode="Markdown")

        # handle different types of Touristic location
        if idx == 0: # Touristic: Yes
            # do something here with database
            #TODO
            bot.sendMessage(from_id, notify_user_wait(),parse_mode="Markdown")
        elif idx == 1: # Touristic: No
            # do something here with database
            #TODO
            bot.sendMessage(from_id, notify_user_wait(),parse_mode="Markdown")
        elif idx == 2: # Touristic: I don't care
            # do something here with database
            #TODO
            bot.sendMessage(from_id, notify_user_wait(),parse_mode="Markdown")

        message_with_inline_keyboard = ask_price_range(bot, from_id)

    elif data == "yes_price" or data == "no_price":
        if data == "yes_price":
            # show feedback to user
            msg_idf = telepot.message_identifier(message_with_inline_keyboard)
            bot.editMessageText(msg_idf, "Got it. User wants to specify a *price range*.", parse_mode="Markdown")

            bot.sendMessage(from_id, price_format(), parse_mode="Markdown")
            global in_price_question
            in_price_question = True

        elif data == "no_price":
            # show feedback to user
            msg_idf = telepot.message_identifier(message_with_inline_keyboard)
            bot.editMessageText(msg_idf, "Got it, no problem.")

            # RECOMMEND HOTEL HERE
            #TODO

    elif data == "start_over" or data == "no_start_over":

        if data == "start_over":
            global started
            message_with_inline_keyboard = None
            started = False
            bot.sendMessage(from_id, welcome_message(),parse_mode="Markdown")
        else:
            bot.sendMessage(from_id, coming_back_reset(),parse_mode="Markdown")


if __name__=="__main__":

    TOKEN = "351129972:AAEFuBELNKPSEmWsi0k7BzxQGZphChBpknI"

    bot = telepot.Bot(TOKEN)
    answerer = telepot.helper.Answerer(bot)

    bot.message_loop({'chat': on_chat_message,
                      'callback_query': on_callback_query})

    print('Listening ...')

    # Keep the program running.
    while 1:
        time.sleep(10)
