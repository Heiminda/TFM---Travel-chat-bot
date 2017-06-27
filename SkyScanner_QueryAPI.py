
# coding: utf-8

# In[1]:

from pymongo import MongoClient
import time
import datetime
from pprint import pprint
import re


# In[2]:

def get_date(fmt, ts=None):
    ts = int(time.time()) if ts is None else int(ts)
    date = datetime.datetime.fromtimestamp(ts).strftime(fmt)
    return date

def parse_date(fmt, date):
    ts = time.mktime(datetime.datetime.strptime(date, fmt).timetuple())
    return ts


# In[3]:

class Agent(object):
    def __init__(self, data):
        self._name = data['Name']
        
    def name(self):
        return self._name
    
    def __str__(self):
        return self.name()

class Price(object):
    def __init__(self, itinerary, data):
        self.itinerary = itinerary
        self._price = data['Price']
        self._agents = data['Agents']
        
    def price(self):
        return self._price
    
    def agent(self):
        return [self.itinerary.flight.agent(id).name() for id in self._agents]
    
    def __str__(self):
        return "{}: {}€".format(self.agent(), self.price())

class Itinerary(object):
    def __init__(self, flight, data):
        self.flight = flight
        self.prices = [Price(self, p) for p in data['PricingOptions']]
        
    def cheapest(self):
        if not self.prices:
            return None
        
        return min(self.prices, key=lambda p: p.price())
        
    def most_expensive(self):
        if not self.prices:
            return None
        
        return max(self.prices, key=lambda p: p.price())

class Flight(object):
    def __init__(self, data):
        self.itineraries = [Itinerary(self, itinerary) for itinerary in data['Itineraries']]
        self.agents = {agent_data['Id']: Agent(agent_data) for agent_data in data['Agents']}
        self._id = data['_id']
        
    def cheapest(self):
        if not self.itineraries:
            return None
        
        return min(self.itineraries, key=lambda it: it.cheapest().price()).cheapest()
    
    def most_expensive(self):
        if not self.itineraries:
            return None
        
        return max(self.itineraries, key=lambda it: it.most_expensive().price()).most_expensive()
    
    def agent(self, id):
        return self.agents[id]
    
    def fake_date(self, dt):
        dt = get_date('%Y-%m-%d', dt)
        self._id['date'] = dt
    
    def date(self):
        return self._id['date']
    
    def date_timestamp(self):
        return parse_date('%Y-%m-%d', self._id['date'])
    
    def departure(self):
        return self._id['departure']
    
    def departure_timestamp(self):
        return parse_date('%Y-%m-%d', self._id['departure'])
    
    def __str__(self):
        return "{{{}->{}}} {} - {}".format(self.date(), self.departure(), self.cheapest(), self.most_expensive())
    
    def is_missing(self):
        return False
    
    
class MisingFlight(object):
    def __init__(self, date):
        self.ts = date
        self.dt = get_date('%Y-%m-%d', date)
        
    def date(self):
        return self.dt
    
    def date_timestamp(self):
        return self.ts
    
    def __str__(self):
        return "{{{}}} Missing".format(self.date())
    
    def is_missing(self):
        return True


# In[4]:

import math
from collections import OrderedDict

class SkyscannerAPI(object):
    def __init__(self, host='localhost'):
        self.client = MongoClient(host)
        self.db = self.client.skyscanner
        self.itineraries = self.db.itineraries
        self.carriers = self.db.carriers
        
    def find_flight(self, departure, origin, destination):
        cursor = self.itineraries.find({
            '_id.departure': departure,
            '_id.origin': origin,
            '_id.destination': destination
        }, {
            '_id': 1,
            'Itineraries.PricingOptions': 1,
            'Agents.Id': 1,
            'Agents.Name': 1
        })
        
        def distribute(sorted_flights):
            i = 0
            total = len(sorted_flights) - 1
    
            dist = []
            while i < total:
                cur = i
                i += 1
                
                while i < total - 1 and sorted_flights[cur].date() == sorted_flights[i].date():
                    i += 1
                    
                diff_in_days = sorted_flights[i].date_timestamp() - sorted_flights[cur].date_timestamp()
                diff_in_days = math.ceil(diff_in_days / (24 * 60 * 60)) - 1
                
                dist.append(sorted_flights[cur])
                
                ts = parse_date('%Y-%m-%d', sorted_flights[cur].date())
                    
                for k in range(int(min(diff_in_days, i - cur))):
                    sorted_flights[cur + k].fake_date(ts + (k + 1) * 24 * 60 * 60)
                    dist.append(sorted_flights[cur + k])
                    
                for k in range(int(diff_in_days - (i - cur))):
                    dist.append(MisingFlight(ts + (k + (i - cur) + 1) * 24 * 60 * 60))
                    
            return dist
        
        sorted_flights = sorted([Flight(data) for data in cursor], key=lambda f: f.date_timestamp())
        sorted_flights = [f for f in sorted_flights if f.cheapest()]
        dist_flights = distribute(sorted_flights)
        unique_flights = OrderedDict([(f.date(), f) for f in dist_flights])
        return list(unique_flights.values())


# In[5]:

if __name__ == '__main__':
    api = SkyscannerAPI('mongodb://skyscanner:skyscanner_tfm@161.116.83.104/skyscanner')
    flights = api.find_flight('2017-06-30', 'BCN', 'EZE')

    for f in flights:
        print(f)

