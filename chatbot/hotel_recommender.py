#coding: utf-8

import pandas as pd
import numpy as np

class HotelRecommender(object):

    def __init__(self, dict_features=None):
        """
        Dict features should be of the form:
            {
            "city": (string),
            "neighbourhood": (string) / None,
            "room": ["Individual", "Double", "More"]
            "centrality": ["Much", "Not much", "Outskirts", "Don't care"],
            "touristic": ["Yes", "Not really", "Don't care"],
            "price": (tuple of type (int,int)) / None
            }
        """
        self.features   = dict_features
        self.db         = pd.read_csv("../hotel_recommendation/trivago_extended.csv", delimiter="\t", header=0)
        self.db_vis     = pd.read_pickle("../trivago_data/pandas_dbs/dataset_visualization.pkl")
        self.preds      = [] # predictions

    def set_features(self, dict_features):
        self.features = dict_features

    def fit(self):

        print("Fitting the recommender to user...")

        city            = self.features["city"]
        neighbourhood   = self.features["neighbourhood"]
        room            = self.features["room"]
        centrality      = self.features["centrality"]
        touristic       = self.features["touristic"]
        price           = self.features["price"]
        feats           = [] # ["value_for_money", "location"]

        df = self.db

        # CITY
        df = df[df['city'] == city]

        # EXTRA FEATURES
        if feats:
            df = self.filter_by_features(df, feats)

        # NEIGHBOURHOOD
        if neighbourhood:
            df = df[df["neighbourhood"] == neighbourhood]

        # ROOM TYPE
        if room == "Individual":
            df = df[df["individual_bed"] == 1]
        elif room == "Double":
            df = df.loc[(df.ix[:,[19,20,21,24]] == 1).any(axis=1)] # at least one true value from [double_bed, king_bed, queen_bed, two_ind_beds]
        elif room == "More":
            df = df.loc[(df.ix[:,[23,25,26,27]] == 1).any(axis=1)] # same for [four_bed, two_ind_beds, five_bed, six_bed, triple]

        # CENTRALITY
        if centrality == "Much":
            df = df[(df['is_hotel_very_centric'] == True) & (df['is_neighbourhood_very_centric'] == True)]
        elif centrality == "Not much":
            df = df.loc[(df['is_hotel_centric'] == True)]
        elif centrality == "Outskirts":
            df = df.loc[(df['is_hotel_very_centric'] == False) & df['is_hotel_centric'] == False]

        # TOURISTIC
        # if touristic == "Yes":
        #     df = df.loc[(df['is_hotel_very_centric'] == True) & df['is_neighbourhood_very_centric'] == True]
        # elif touristic == "Not really":
        #     df = df.loc[(df['is_hotel_centric'] == True)]

        # PRICE
        if price:
            df = df[df["price"].astype(np.float64).between(price[0], price[1], inclusive=True)]

        # sort hotels by rating values?
        df = df.ix[df.ix[:,9:18].mean(axis=1).sort_values(ascending=False).index]

        self.preds = df.hotel_name

        print("Done.")

    def show_n_predictions(self, N=5, show_next=None):
        """ Returns a string with the information of the N best hotel predictions """

        # returns the visualization info of the N best hotels
        if show_next:
            data = self.db_vis[self.db_vis.name.isin(self.preds.values[N:min(N+show_next,len(self.preds.values)-1)])]
        else:
            data = self.db_vis[self.db_vis.name.isin(self.preds.values[:N])]

        string_preds = []

        for n,row in enumerate(data.iterrows()):

            row = row[1]
            top_result_n = str(N + n + 1) if show_next else str(n + 1)
            s =  "\n ---------- Top *%s* result ----------\n\n" % top_result_n
            s += "\tHotel name:\t %s\n" % str(row["name"])
            s += "\tPrice:\t\t %s €/night\n" % str(row.price)
            s += "\tStar count:\t %s\n\n" % str(row.star_count)
            s += "\tContact info:\n"
            s += "\t\t %s\n" % str(row.phone)
            s += "\t\t\t %s\n" % str(row.web)
            s += "\t\t\t %s\n\n" % str(row.email)
            s += "\tStreet:\t\t *%s*\n" % str(row.street)
            s += "\tNeighbourhood:\t %s" % str(row.neighbourhood)

            string_preds.append(s)

        return string_preds


    def filter_by_features(self, df, features):
        # Select hotels with specific features (all cases)
        tri_ranking = df.loc[:,u'breakfast':u'value_for_money']
        hotels = dict.fromkeys(df[u'hotel_name'],[])
        n = range(len(df))
        # Features selected with a minimum ranking of 80/100, asure good rating
        for hotel, i in zip (df[u'hotel_name'], n):
            hotels[hotel] = list(tri_ranking.columns[np.where(tri_ranking.iloc[i].astype('float')>80)[0]])
        # Selecting hotels which contain features
        hotels_amb_features =[hotel for hotel,hotel_features in zip(hotels,hotels.values()) if set(features) <= set(hotel_features)]
        filtered_centric = df.loc[df['hotel_name'].isin(hotels_amb_features)]
        return filtered_centric
