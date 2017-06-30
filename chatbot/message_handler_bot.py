# coding: utf-8
import numpy as np

def welcome_message():
    return "*Welcome to Travel Chatbot!* \
            \n\nHere I will recommend you flights and hotels according to your preferences. \
            \n\n- In order to start using our bot, please type */start*. \
            \n- If you want to quit the process, just type */quit* anytime. \
            \n- If you want to repeat the process, type */repeat*."

def ask_first_question():
    return "Okay, thank you for start using me. \
            \n\nNow I ask you to choose one among the different options that I offer:\n \
            \n\t\t*Flight*: Given a from-to airport and a departure date, I will recommend you the best day to buy the flight.\
            \n\n\t\t*Hotel*: There I will recommend you an hotel from any city we provide according to your preferences.\
            \n\n\t\t*Both*: There I will recommend you both flight and hotel!\n"

def bye_message():
    return "Thank you for using Travel Chatbot. See you next time!"

def hotel_rec_starter():
    return "Great! You just entered the *hotel recommender mode*. \
            \nDuring this mode, we will recommend you an hotel according to your preferences.\
            \n\nWe will ask you a couple questions in order to improve the recommendation performance."

def ask_quit():
    return "You typed quit command. Are you sure you want to *quit* the whole process?\
            \nNote that all your settings will be *lost* if so."

def ask_repeat():
    return "You typed repeat command. Are you sure you want to *repeat* the whole process?\
            \nNote that all your settings will be *lost* if so."

def coming_back_reset():
    return "Okay, then you must interact with the _last question_ I asked, please."

def ask_flight_from():
    return "Please write the *departure city*"

def ask_flight_to():
    return "Please write the *destination city*. Note that it has to be *Barcelona* since we do not support any other city yet..."

def notify_user_wait():
    return "Please wait, I am doing things on background..."

def ask_city_question():
    return "Which city would you like to go?"

def ask_roomtype_question():
    return "What kind of room would you like to stay in"

def ask_neighbourhood_1():
    return "Would you like to choose a specific neighbourhood for the hotel?"

# neighbourhoods is a list of strings
def ask_neighbourhood_2(neighbourhoods, num_hotels):
    numbers = [str(i) for i in range(len(neighbourhoods))]
    return "Which one?\n\n" + '\n'.join(["*"+numbers[i] + "* -\t*" + neigh + "* (%d hotels)" % num_hotels[neigh] for i,neigh in enumerate(neighbourhoods)])

def ask_mode_neighbourhood():
    return "How would you like to select the neighbourhood?"

def ask_write_neighbourhood():
    return "Please, you must now write down the desired neighbourhood. It is not necessary to spell it perfectly, I will do it for you."

def ask_write_neighbourhood_again():
    return "Okay, write down again your desired neighbourhood:"

def ask_write_neighbourhood2(nearest_neighs, num_hotels, is_dict):
    if is_dict:
        nearest_neighs_ = list(nearest_neighs)
        nearest_neighs_.append("None of them")
    else:
        nearest_neighs_ = [nearest_neighs]
        nearest_neighs_.append("Nope")
    numbers = [str(i) for i in range(len(nearest_neighs_))]
    if is_dict:
        s = "Which one do you mean?\n"
    else:
        s = "Do you mean this one?\n"
    for i, n in enumerate(nearest_neighs_):
        if i != len(nearest_neighs_) - 1:
            if is_dict:
                s += "\n*" + numbers[i] + "* -\t*" + n + "* (%d hotels)" % num_hotels[n]
            else:
                s += "\n*" + numbers[i] + "* -\t*" + n + "* (%d hotels)" % num_hotels
        else:
            s += "\n*" + numbers[i] + "* -\t" + n
    return s

def ask_write_flight_city(nearest_cities, is_list):
    if is_list:
        nearest_cities_ = list(nearest_cities)
        nearest_cities_.append("None of them")
    else:
        nearest_cities_ = [nearest_cities]
        nearest_cities_.append("Nope")
    numbers = [str(i) for i in range(len(nearest_cities_))]
    if is_list:
        s = "Which one do you mean?\n"
    else:
        s = "Do you mean this one?\n"
    for i, n in enumerate(nearest_cities_):
        s += "\n*" + numbers[i] + "* -\t" + n
    return s

def choose_airport(airports):
    s = "Okay. Which airport?\n"
    for i, n in enumerate(airports):
        s += "\n*" + str(i) + "* -\t" + n
    return s

def ask_departure_date():
    return "Now you are asked to give your desired departure date in the format\n\n\t\t _YYYY-MM-DD_"

def wrong_departure_date_format():
    return "Wrong format, remember that you should provide any desired date in the format _YYYY-MM-DD_. Please write it again."

def not_valid_date():
    return "This is not a valid date. Remember that the departure date should be at least a day ahead from today! Please write it again."

def rec_flight(rec, airport_dict):
    day, price, origin, dest = rec
    for k, v in airport_dict.iteritems():
        if origin in v:
            city = k
            break
    return "My recommendation is:\
            \n\nBuy the ticket on day: *%s*\
            \nEstimated best price: *%.2f eur*\
            \nOrigin Airport: *%s, %s*\
            \nDestination Airport: *%s,%s*" % (day, price, origin, city, dest, "Barcelona")

def ask_to_follow_to_hotel():
    return "Nice, you have just finished my flight recommendation process.\
        \n\nIf you want, you can continue using my services and get an hotel recommendation in the destination city."

def ask_central():
    return "How much central would you like the hotel to be placed?"

def ask_touristic():
    return "Do you want it to be in a touristic hot zone?"

# prices is a list of price values (numpy array)
def price_range_stats(prices):
    if len(prices) >= 1:
        s = "Now you have the option to select a price range for your hotel preferences. \
            \n\nFirst let's see some statistics: \
            \n\t\tNumber of hotels found: *" + str(len(prices))+ "*\
            \n\t\tMean price: *" + str(np.round(np.mean(prices),2))+ "*\
            \n\t\tMin price: *" + str(np.round(np.min(prices),2)) + "*\
            \n\t\tMax price: *" + str(np.round(np.max(prices),2)) + "*"
    else:
        s = "Ups, this is embarassing. I did not find any hotel according to your hotel prefrences..."
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
    s = "These are the filters I inferred from you:\n"
    s += "\n".join(["\t"+ k + " : *" + str(v) + "*" for k,v in feats.iteritems() if k != "cityInt"])
    return s

def ask_recommendation_followup():
    s = "These were my recommendations. "
    s += "You now can either see more of them by pressing 'Show more' button, "
    s += "or finish the process by pressing 'Done'."
    return s

def ask_recommendation_followup2():
    return "These were my recommendations.\nYou can now finish the process by pressing 'Done'."

def ask_review_user():
    s = "Superb!\n\n"
    s += "In order to improve my recommender system performance, I have to ask you to write a *short review* explaining "
    s += "what you liked or not liked about the hotel recommendations.\n\n"
    s += "Here are a couple of review suggestions that could work:\n\n"
    s += "\t_Everything was fine._\n"
    s += "\t_It worked._\n"
    s += "\t_Location is nice. But prices are unaffordable, too high._\n"
    return s

def ask_review_user2():
    s = "Okay.\n\n"
    s += "Please, write a review again.\n\n"
    s += "Here are a couple of review suggestions that could work:\n\n"
    s += "\t_Everything was fine._\n"
    s += "\t_It worked._\n"
    s += "\t_Location is nice. But prices are unaffordable, too high._\n"
    return s

def explain_sentiment_results(results):

    s = "Okay, I have just analysed your review and I found the following topics:\n"
    for topic, score in results["topics"]:
        s += "\n\t"
        if score == 1:
            s += "*"+str(topic)+"*" + " : " + "*Positive*"
        else:
            s += "*"+str(topic)+"*" + " : " + "*Negative*"

    s += "\n\nThe overall sentiment of the review is *" + results["sentiment"] + "*"
    s += " with a *%.2f%%* of confidence." % (results["confidence"] * 100.)
    return s

def sent_analysis_confirmation():
    s = "Thank you so much! This will definitely help my recommendation performances."
    s += " I am now storing the results in our dataset...\n\n"
    s += "If you want to start the process again please type */start*."
    return s
