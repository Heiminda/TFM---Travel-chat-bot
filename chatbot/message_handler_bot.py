# coding: utf-8
import numpy as np

def welcome_message():
    return "*Welcome to Yogi Chatbot!* \
            \n\nHere we will recommend you flights and hotels according to your preferences. \
            \nIn order to start using our bot, please type */start*. \
            \nIf you want to quit the process, just type */q* anytime. \
            \nIf you want to repeat the process, type */start* again."

def bye_message():
    return "Thank you for using Yogi Chatbot. See you next time!"

def hotel_rec_starter():
    return "Great! You just entered the *hotel recommender mode*. \
            \nDuring this mode, we will recommend you an hotel according to your preferences.\
            \n\nWe will ask you a couple questions in order to improve the recommendation performance."

def ask_quit():
    return "You typed quit command. Are you sure you want to *quit* the whole process?\
            \nNote that all your settings will be *lost* if so."

def coming_back_reset():
    return "Okay, then you must interact with the _last question_ you were asked, please."

def notify_user_wait():
    return "Please wait, I am doing things on background..."

def ask_city_question():
    return "Which city would you like to go?"

def ask_roomtype_question():
    return "What kind of room would you like to stay in"

def ask_neighbourhood_1():
    return "Would you like to choose a specific neighbourhood for the hotel?"

# neighbourhoods is a list of strings
def ask_neighbourhood_2(neighbourhoods):
    numbers = [str(i) for i in range(len(neighbourhoods))]
    return "Which one?\n\n" + '\n'.join(["*"+numbers[i] + "* -\t" + neigh for i,neigh in enumerate(neighbourhoods)])

def ask_central():
    return "How much central would you like the hotel to be placed?"

def ask_touristic():
    return "Do you want it to be in a touristic hot zone?"

# prices is a list of price values (numpy array)
def price_range_stats(prices):
    s = "Now you have the option to select a price range for your hotel preference. \
        \n\nFirst let's see some statistics: \
        \n\t\tMean price: *" + str(np.round(np.mean(prices),2))+ "*\
        \n\t\tMin price: *" + str(np.round(np.min(prices),2)) + "*\
        \n\t\tMax price: *" + str(np.round(np.max(prices),2)) + "*\
        \n\t\tStandard deviation: *" + str(np.round(np.std(prices),2)) + "*"
    return s

def ask_if_price_range():
    return "Would you like to give a price range for your hotel recommendation?"

def price_format():
    return "Now you should type in a price range in the correct format. \
            \nRemember to give a price range *within the real range* (see Min Price and Max Price in the stats). \
            \nThe range format should be: *int*_<space>_*int*\
            \nExample: *100 200*"

def price_format_wrong():
    return "Wrong format. Try again please. \
            \nRemember to give a price range *within the real range* (see Min Price and Max Price in the stats). \
            \nThe range format should be: *int*_<space>_*int*\
            \nExample: *100 200*"

def print_features(feats):
    s = "These are the filters we infered from you. Please, check if they are correct:\n"
    s += "\n".join(["\t"+ k + " : *" + str(v) + "*" for k,v in feats.iteritems()])
    s += "\n\n\nWould you like to change them?"
    return s
