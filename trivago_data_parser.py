#coding: utf-8

import json
import numpy as np
import pandas as pd
from unidecode import unidecode
import pickle

# See trivago_data_parser.ipynb for dataset column specifications

class DataHandler():

    def __init__(self, txt_files):
        self.txt_files = txt_files

    def get_hotel_names(self):
        names = []
        for txt in self.txt_files:
            with open(txt,"r") as f:
                lines = f.readlines()
            for line in lines:
                dat = json.loads(line)
                names.append(unidecode(dat["name"]))

        return list(np.unique(names))

    def get_values_from(self, attribute):
        # returns a list with the values of the specified attribute
        values = []

        for txt in self.txt_files:
            with open(txt,"r") as f:
                lines = f.readlines()
            values_txt = []
            for line in lines:
                dat = json.loads(line)
                info = dat[attribute]
                if info:
                    for elem in info:
                        val = unidecode(elem)
                        if val not in values:
                            values.append(val)
        return list(np.unique(values))

    def get_all_values_ratings(self):
        values = []

        for txt in self.txt_files:
            with open(txt,"r") as f:
                lines = f.readlines()
            values_txt = []
            for line in lines:
                dat = json.loads(line)
                rats = dat["ratings"] # list of lists
                for rat in rats:
                    val = unidecode(rat[1]) #  rat[0] rating / rat[1] name of rating
                    if val not in values:
                        values.append(val)
        return list(np.unique(values))

    def get_all_partners(self):
        values = []

        for txt in self.txt_files:
            with open(txt,"r") as f:
                lines = f.readlines()
            values_txt = []
            for line in lines:
                dat = json.loads(line)
                rats = dat["reviewPartners"] # list of lists
                for rat in rats:
                    val = unidecode(rat[0]) # rat[0] partner_name / rat[1] review_counts for partner / rat[2] rating
                    if val == "Otras fuentes":
                        continue
                    elif val not in values:
                        values.append(val)
        return list(np.unique(values))

    def get_all_top_features(self):
        values = []

        for txt in self.txt_files:
            with open(txt,"r") as f:
                lines = f.readlines()
            values_txt = []
            for line in lines:
                dat = json.loads(line)
                feats = dat["topFeatures"] # list of lists
                for feat in feats:
                    val = unidecode(feat[0]) # 0: feat["title"], 1: feat["isAvailable"], 2: feat["isFreeOfCharge"]
                    if val not in values:
                        values.append(val)
        return list(np.unique(values))

        # edit while you are getting more data from other cities
    def parse_city_name(self, name):
        if name == "BarcelonaCap1" or name == "BarcelonaCap2":
            return 1
        elif name == "BarcelonaProv":
            return 2
        elif name == "London":
            return 3
        else:
            return 0

    # execute only this method
    def get_attributes(self):
        adequate_for_names = self.get_values_from("adequateFor")
        available_beds_names = self.get_values_from("availableBeds")
        rating_names = self.get_all_values_ratings()
        partner_names = self.get_all_partners()
        top_features = self.get_all_top_features()
        type_names = self.get_values_from("type")
        type_dict = {type_names[i]:i for i in range(len(type_names))}

        return [adequate_for_names, available_beds_names, rating_names, partner_names, top_features, type_dict]


class Parser():

    def __init__(self, cities, txt_files):
        self.data_handler = DataHandler(txt_files)
        self.cities = cities # List of city names
        self.txt_files = txt_files

    def parse_data(self):

        data_gen = np.zeros([1,84])

        vis_columns = ["city", "name","email","phone","postal_code","price","star_count","street","type","web"] # falta neighbourhood
        vis_df = pd.DataFrame(data=np.zeros([1,len(vis_columns)]), columns=vis_columns)
        print vis_df
        attributes = self.data_handler.get_attributes()

        hotel_names_gen = [] # to avoid duplicates
        hotel_names_vis = [] # to avoid duplicates

        for city in self.cities:
            if city == "Barcelona":
                print city
                for text_file in self.txt_files:
                    city_data, hotel_names_gen = self.parse_data_generator(city, text_file, attributes, hotel_names_gen)
                    data_gen = np.concatenate((data_gen, city_data), axis = 0)

                    city_data_vis, hotel_names_vis = self.parse_data_visualizer(city, text_file, hotel_names_vis, vis_columns)
                    vis_df = vis_df.append(city_data_vis, ignore_index=True)

        return data_gen[1:,], vis_df.ix[1:,:]

    def parse_data_visualizer(self, city_name, text_file, hotel_names, columns):

        hnames = hotel_names

        with open(text_file, "r") as f:
            lines = f.readlines()

        data = []

        c = 0

        for j,line in enumerate(lines):

            dat = json.loads(line)

            if dat["name"] not in hnames: #not repeated

                data_line = []

                hnames.append(dat["name"])
                
                data_line.append(unidecode(city_name))
                
                try:
                    data_line.append(unidecode(dat["name"]))
                except:
                    data_line.append("")

                try:
                    data_line.append(unidecode(dat["email"]))
                except:
                    data_line.append("")

                try:
                    data_line.append(unidecode(dat["phone"]))
                except:
                    data_line.append("")

                try:
                    data_line.append(unidecode(dat["postalCode"]))
                except:
                    data_line.append("")

                try:
                    data_line.append(unidecode(dat["price"]))
                except:
                    data_line.append("")

                try:
                    data_line.append(str(dat["starCount"]))
                except:
                    data_line.append("")

                try:
                    data_line.append(unidecode(dat["street"]))
                except:
                    data_line.append("")

                try:
                    data_line.append(dat["type"]) # could be a list >= 1 element
                except:
                    data_line.append("")

                try:
                    data_line.append(unidecode(dat["web"]))
                except:
                    data_line.append("")

#                 try:
#                     # data_line.append(unidecode(dat["neighbourhood"])) # TODO: neighbourhood
#                 except:
#                     data_line.append("")
                 # add data line
                data.append(data_line)
            else:
                c += 1

        return pd.DataFrame(data, columns=columns), hnames

    # input is a dict in which each key is the city name with its text_file_path
    def parse_data_generator(self, city_name, text_file, attributes, hotel_names):

        hnames = list(hotel_names)

        if attributes is not None:

            with open(text_file,"r") as f:
                lines = f.readlines()

            adequate_for_names = attributes[0]
            available_beds_names = attributes[1]
            rating_names = attributes[2]
            partner_names = attributes[3]
            top_features = attributes[4]
            type_dict = attributes[5]

            data = np.empty([1,84])
            c = 0
            for j,line in enumerate(lines):

                data_line = []
                dat = json.loads(line)

                if dat["name"] not in hnames: # not repeated

                    hnames.append(dat["name"])

                    data_line.append(dat["name"])
                    data_line.append(self.data_handler.parse_city_name(city_name))
                    data_line.append(dat["price"])
                    data_line.append(1 if dat["has_quality_test"] == True else 0)
                    data_line.append(dat["hotel_total_rating"] if dat["hotel_total_rating"] else 0)
                    data_line.append(1 if dat["isPremiumPartner"] == True else 0)
                    data_line.append(dat["latitude"] if dat["latitude"] else 0)
                    data_line.append(dat["longitude"] if dat["longitude"] else 0)
                    data_line.append(dat["partnerReviewCount"] if dat["partnerReviewCount"] else 0)

                    # ratings
                    init = np.zeros(len(rating_names), dtype=np.int32)
                    names = {unidecode(elem[1]):elem[0] for i,elem in enumerate(dat["ratings"])}

                    for i,name in enumerate(rating_names):
                        if name in names.keys():
                            init[i] = names[name]

                    for elem in init:
                        data_line.append(elem)

                    # available_beds
                    init = np.zeros(len(available_beds_names), dtype=np.int32)
                    if dat["availableBeds"]:
                        bed_names = [unidecode(elem) for elem in dat["availableBeds"]]

                        for i,name in enumerate(available_beds_names):
                            if name in bed_names:
                                init[i] = 1

                    for elem in init:
                        data_line.append(elem)

                    # adequate for
                    init = np.zeros(len(adequate_for_names))
                    if dat["adequateFor"]:
                        names = [unidecode(elem) for elem in dat["adequateFor"]]

                        for i,name in enumerate(adequate_for_names):
                            if name in names:
                                init[i] = 1

                    for elem in init:
                        data_line.append(elem)

                    # partners
                    init1 = np.zeros(len(partner_names)) # this is for rating counts
                    init2 = np.zeros(len(partner_names)) # this is for ratings

                    if dat["reviewPartners"]:
                        names = {unidecode(elem[0]):(elem[1],elem[2]) for i,elem in enumerate(dat["reviewPartners"])}

                        for i, name in enumerate(partner_names):
                            if name in names.keys():
                                init1[i] = names[name][0]  # partnername_rc

                        for i, name in enumerate(partner_names):
                            if name in names.keys():
                                init2[i] = names[name][1] # partnername_r

                    for elem in np.concatenate([init1,init2]):
                        data_line.append(elem)

                    # top features
                    init1 = np.zeros(len(top_features)) # if feature available
                    init2 = np.zeros(len(top_features)) # if feature is free of charge

                    if dat["topFeatures"]:
                        names = {unidecode(elem[0]):(elem[1],elem[2]) for i,elem in enumerate(dat["topFeatures"])}

                        for i, name in enumerate(top_features):
                            if name in names.keys():
                                init1[i] = 0 if names[name][0] == False else 1  # isavailable

                        for i, name in enumerate(top_features):
                            if name in names.keys():
                                init2[i] = 0 if names[name][1] == False else 1  # isfreeofcharge

                    for elem in np.concatenate([init1,init2]):
                        data_line.append(elem)

                    # hotel_type
                    if dat["type"]:
                        data_line.append(type_dict[unidecode(dat["type"][0])])
                    else:
                        data_line.append(-1)
                    data_line = np.asarray(data_line)[np.newaxis, :]

                    # add data line
                    try:
                        data = np.concatenate((data,data_line), axis=0)
                    except Exception:
                        print np.round(data_line)
                        print j
                        break
                else:
                    c += 1

            return data[1:,], hnames
        else:
            return None


if __name__ == '__main__':

    # FILL THESE DETAILS BY YOURSELF
    txt1 = "trivago_data/Barcelona/trivago_BarcelonaCap_31965_7_1_2017-03-20_16:21:50.txt"
    txt2 = "trivago_data/Barcelona/trivago_BarcelonaCap_31965_1_1_2017-03-20_15:49:03.txt"
    txt3 = "trivago_data/Barcelona/trivago_BarcelonaProv_344066_1_1_2017-03-15_12:00:28.txt"

    city_names = ["Barcelona"]
    txts = [txt1,txt2,txt3]

    parser = Parser(city_names, txts)
    print "Getting data..."
    data_gen, data_vis = parser.parse_data()
    print "Done."
    print "Data shape:", data_gen.shape
    print "Data vis shape:", data_vis.shape

    file_to_store = "trivago_data/pandas_dbs/dataset.pkl" # pickle file
    file_to_store_vis = "trivago_data/pandas_dbs/dataset_visualization.pkl"

    print "Creating pandas databases and storing them in:", file_to_store, "and", file_to_store_vis

    columns = ["hotel_name",
            "city",
            "price",
            "quality_test",
            "total_rat",
            "premium",
            "lat",
            "lon",
            "part_total_rat",
            "breakfast",
            "cleanliness",
            "comfort",
            "facilities",
            "food",
            "hotel_condition",
            "location",
            "room",
            "service",
            "value_for_money",
            "double_bed",
            "king_bed",
            "queen_bed",
            "individual_bed",
            "four_bed",
            "two_ind_beds",
            "five_bed",
            "six_bed",
            "triple",
            "water_sports",
            "winter_sports",
            "family",
            "party",
            "fitness",
            "gay_friendly",
            "gourmets",
            "big_groups",
            "honey_moon",
            "business",
            "adults_only",
            "single_status",
            "pet_travelers",
            "atrapalo_rc",
            "customer_alliance_rc",
            "expedia_rc",
            "holiday_check_rc",
            "hoteles_rc",
            "hotelsclick_rc",
            "splendia_rc",
            "superbreak_rc",
            "vinivi_rc",
            "zoover_rc",
            "hostelbookers_rc",
            "atrapalo_r",
            "customer_alliance_r",
            "expedia_r",
            "holiday_check_r",
            "hoteles_r",
            "hotelsclick_r",
            "splendia_r",
            "superbreak_r",
            "vinivi_r",
            "zoover_r",
            "hostelbookers_r",
            "air_conditioner",
            "bar_in_hotel",
            "gym",
            "pet_allowed",
            "parking",
            "pool",
            "restaurant",
            "spa",
            "wifi_room",
            "wifi_hall",
            "air_conditioner_free",
            "bar_in_hotel_free",
            "gym_free",
            "pet_allowed_free",
            "parking_free",
            "pool_free",
            "restaurant_free",
            "spa_free",
            "wifi_room_free",
            "wifi_hall_free",
            "hotel_type"]

    dataset = pd.DataFrame(data=data_gen, columns=columns)

    # store it as a pickle file
    dataset.to_pickle(file_to_store)
    data_vis.to_pickle(file_to_store_vis)

    # to load it back
    # dataset = pd.read_pickle(file_to_store)

    print "Done. Quitting..."
