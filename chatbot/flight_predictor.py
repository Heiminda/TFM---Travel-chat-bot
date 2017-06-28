#coding utf-8

import numpy as np
from datetime import datetime as dtime
import pandas as pd
import datetime
import cPickle
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder

class FlightPredictor():

    def __init__(self, regressor_file, oilcsv_file):
        print "Initializing Flight Predictor...",
        self.oil_prices     = self.init_oil(oilcsv_file)
        self.rfregressor    = self.init_regressor(regressor_file)
        self.airport, self.airport_cities, self.airport_dict = self.init_airport()
        self.airport_array  = np.array(self.airport)
        self.encoder        = self.init_encoder()
        print "Done"
    def init_oil(self, oilcsv):
        Oil_prices = pd.read_csv(oilcsv)
        Oil_prices.DCOILBRENTEU[Oil_prices.DCOILBRENTEU == '.'] = float('nan')
        Dates = [(dtime.today().date() - datetime.timedelta(days=x)).isoformat() for x in range(0, 365)]
        Dates = pd.DataFrame({'DATE': Dates})
        Oil_prices = Oil_prices.merge(Dates,how = 'right').sort_values('DATE').fillna(method = 'ffill')
        return Oil_prices

    def init_regressor(self, rfile):
        with open(rfile, "rb") as f:
            reg = cPickle.load(f)
        return reg

    def init_airport(self):
        airport = ['LCY', 'LHR', 'LGW', 'LTN', 'SEN', 'STN',
                   'CDG', 'ORY', 'BVA',
                   'MAD',
                   'ATH',
                   'FCO','CIA',
                   'BRU', 'CRL',
                   'BER', 'SXF',
                   'DME', 'SVO',
                   'SFO',
                   'JFK',
                   'PEK',
                   'EZE',
                   'GIG',
                   'DEL']
        airport_cities = ['london','london','london','london','london','london','paris','paris','paris','madrid','athens','rome','rome',
                         'brussels','brussels','berlin','berlin','moscow','moscow','san francisco','new york','beijing','buenos aires',
                         'rio de janeiro','new delhi']
        airport_dict = {"London": airport[0:6],
                        "Paris": airport[6:9],
                        "Madrid": [airport[9]],
                        "Athens": [airport[10]],
                        "Rome": airport[11:13],
                        "Brussels": airport[13:15],
                        "Berlin": airport[15:17],
                        "Moscow": airport[17:19],
                        "San Francisco": [airport[19]],
                        "New York": [airport[20]],
                        "Beijing": [airport[21]],
                        "Buenos Aires": [airport[22]],
                        "Rio de Janeiro": [airport[23]],
                        "New Delhi": [airport[24]]}
        return airport, airport_cities, airport_dict

    def get_airport_cities(self):
        return self.airport_dict.keys()

    def find_airports_from_city(self, city):
        if city in self.airport_dict.keys():
            return self.airport_dict[city]

    def get_city_from_airport(self, airport):
        for k, v in self.airport_dict.iteritems():
            if airport in v:
                return k
        return None

    def get_airport_dict(self):
        return self.airport_dict

    def init_encoder(self):
        to_encode = []
        for i in range(25):
            for j in range(7):
                for k in range(7):
                    for l in range(12):
                        to_encode.append([i,j,k,l+1])
        enc = OneHotEncoder()
        enc.fit(to_encode)
        return enc

    def predict_lowest_price(self, departure_date, destination):
        Rfregressor_air = self.rfregressor[destination]
        today = dtime.today().date()
        departure_date = dtime.strptime(departure_date, '%Y-%m-%d').date()
        predict2 = []
        predict = []
        date = today
        for i in range((departure_date-today).days):
            date = today + datetime.timedelta(days=i)
            predict2.append([self.airport.index(destination),
                      date.weekday(),
                      departure_date.weekday(),
                      departure_date.month])
            predict.append([(departure_date-date).days,
                          float(self.oil_prices[self.oil_prices.DATE == today.isoformat()].DCOILBRENTEU.values[0])])
        predict3 = np.c_[predict, self.encoder.transform(predict2).toarray().tolist()]
        prediction = Rfregressor_air.predict(predict3)
        #return prediction
        days_wait_to_buy = [k1  for k1, k2 in enumerate(prediction) if k2 == min(prediction) ][0]
        price = min(prediction)
        return (today + datetime.timedelta(days=days_wait_to_buy) ).isoformat(), price, destination

    def find_best_flight(self, options):
        if options["to"] in self.airport:
            day, price, airport = self.predict_lowest_price(options["when"], options["to"])
            return day, price, airport
        else:
            dest = options["to"].lower()
            airs = self.airport_array[[k for k,city in enumerate(self.airport_cities) if city == dest]]
            minprice = 1e10
            for air in airs:
                day, price, airport = self.predict_lowest_price(options["when"], air)
                if price < minprice:
                    minprice = price
                    minday = day
                    minairport = airport
            return day, price, airport

    # usage: flight_regressor.find_best_flight('2017-08-04','LCY')
    # usage: flight_regressor.find_best_flight('2017-08-04','London')
