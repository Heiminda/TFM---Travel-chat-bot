#coding: utf-8

import pandas as pd
import numpy as np
from urlparse import urlparse

class HotelRecommender(object):

    def __init__(self, dict_features=None):
        self.features   = dict_features
        self.db         = pd.read_csv("trivago.csv", sep="\t").ix[:,1:]
        self.preds      = [] # predictions

    def set_features(self, dict_features):
        self.features = dict_features

    def fit(self):

        print("Fitting the recommender to user...")
        city            = self.features["cityInt"]
        neighbourhood   = self.features["neighbourhood"]
        # room            = self.features["room"]
        centrality      = self.features["centrality"]
        price           = self.features["price"]
        feats           = [] # ["value_for_money", "location"]

        df = self.db.copy()
        # CITY
        df = df[df['city_int'] == city]

        # EXTRA FEATURES
        if feats:
            df = self.filter_by_features(df, feats)

        # NEIGHBOURHOOD
        if neighbourhood:
            df = df[df["neighbourhood"] == neighbourhood]
        # CENTRALITY
        else:
            if centrality == "Much":
                df = df[df['is_hotel_very_centric'] == True]
            elif centrality == "Not much":
                df = df.loc[df['is_hotel_centric'] == True]
            elif centrality == "Not at all":
                df = df.loc[(df['is_hotel_very_centric'] == False) & df['is_hotel_centric'] == False]
            else:
                df = df.loc[df['is_neighbourhood_very_centric'] == True]

        # PRICE
        if price is not None:
            min_price = df["price"].min()
            max_price = df["price"].max()

            df = df[(df['price'] >= max(price[0], min_price)) & (df['price'] <= min(price[1], max_price))]

        # sort hotels by rating values?
        df = df.ix[df.ix[:,9:18].mean(axis=1).sort_values(ascending=False).index]

        self.preds = df.hotel_name
        success = len(self.preds) != 0
        return success, len(self.preds)

    def show_n_predictions(self, N=5, show_next=None):
        """ Returns a string with the information of the N best hotel predictions """

        # returns the visualization info of the N best hotels
        if show_next:
            data = self.db[self.db.hotel_name.isin(self.preds.values[N:min(N+show_next,len(self.preds.values)-1)])]
        else:
            data = self.db[self.db.hotel_name.isin(self.preds.values[:N])]

        string_preds = []

        for n,row in enumerate(data.iterrows()):

            row = row[1]
            top_result_n = str(N + n + 1) if show_next else str(n + 1)
            s =  "\n ---------- Top *%s* result ----------\n\n" % top_result_n
            s += "\tHotel name:\t %s\n" % str(row["hotel_name"])
            s += "\tPrice:\t\t %s eur/night\n" % str(row.price)
            s += "\tStar count:\t %s\n\n" % str(row.star_count) if row.phone else "-No phone available-"
            s += "\tContact info:\n"
            s += "\t\t %s\n" % str(row.phone) if row.phone else "**No phone available**"
            s += "\t\t\t %s\n" % urlparse(str(row.web)).netloc if row.web else "**No web available**"
            s += "\t\t\t %s\n\n" % str(row.email) if row.email else "**No email available**"
            s += "\tStreet:\t\t *%s*\n" % str(row.street) if row.street else "**No street available**"
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
