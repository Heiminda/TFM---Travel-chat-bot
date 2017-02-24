
# coding: utf-8

# In[1]:

import sys
import os
import urllib
import requests
import time
import datetime
import threading
import logging
import json
import pymongo
from itertools import cycle
from Queue import Queue
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor


# In[4]:

def do_request(request_type, url, data, apikey):
    logger.info('[REQ] ' + url)
    return http_pool.submit(do_request_imp, request_type, url, data, apikey).result()
    #return do_request_imp(request_type, url, data, apikey)

def do_request_imp(request_type, url, data, apikey):
    def get_method(request_type):
        return getattr(requests, request_type)
    
    headers = {'Cache-control': 'no-cache, no-store, must-revalidate'}
    payload = None
    
    if request_type != 'get':
        if type(data) == str or type(data) == unicode:
            payload = data + '&apikey=' + apikey
        else:
            data['apikey'] = apikey
            payload = urllib.urlencode(data)
    
        headers['content-type'] = 'application/x-www-form-urlencoded'
    else:
        url += '?apikey=' + apikey
    
    r = get_method(request_type)(url, data=payload, headers=headers)
    return r


def parse_request(r, apikey):
    if r.status_code == 201:
        return do_request('get', r.headers['Location'], {}, apikey)
    
    return r


# In[5]:

def fetch_data(origin, destination, when, apikey):
    data = {
        'cabinclass': 'Economy',
        'country': 'ES',
        'currency': 'EUR',
        'locale': 'en-GB',
        'locationSchema': 'iata',
        'originplace': origin,
        'destinationplace': destination,
        'outbounddate': when,
        'adults': '1',
        'children': '0',
        'infants': '0'
    }

    return do_request('post', 'http://partners.api.skyscanner.net/apiservices/pricing/v1.0', data, apikey)

def keep_polling(func, tries, fail_wait, apikey):
    def _inner(*args, **kwargs):
        current_try = 0
        
        while current_try < tries:
            r = func(*args, apikey=apikey, **kwargs)

            r_poll = None
            pending_session = 0
            while (r_poll == None or r_poll.status_code == 304) and pending_session < 5:
                logger.info("\t[WAIT] Waiting %ds for session to be created" % (pending_session * 2 + 1))
                time.sleep(pending_session * 2 + 1) # Let session be created
                r_poll = parse_request(r, apikey)
                pending_session += 1

            if r_poll.status_code == 200:
                return r_poll.text.encode('utf-8')
            
            current_try += 1
            if current_try < tries:
                logger.error("\t[FAIL] Reattempting in %d seconds (reason: %d)" % (fail_wait, r_poll.status_code))
                time.sleep(fail_wait)

        return None
    
    return _inner


# In[6]:

def get_date(fmt, ts=None):
    ts = int(time.time()) if ts is None else int(ts)
    date = datetime.datetime.fromtimestamp(ts).strftime(fmt)
    return date

def fetch_and_save(origin, destination, when, apikey, tries=3, fail_wait=10):
    logger.info("[DO] %s to %s on %s" % (origin, destination, when))
    
    date = get_date('%Y-%m-%d-%H')
    filename = '%s_%s_%s_%s.json' % (origin, destination, date, when)
    filename = os.path.join('flights-data', filename)
    
    try:
        os.makedirs('flights-data')
    except:
        pass
    
    data = keep_polling(fetch_data, tries, fail_wait, apikey)(origin, destination, when)
    if data is None:
        logger.error("[ERROR] %s to %s on %s, apikey=%s" % (origin, destination, when, apikey))
    else:
        with open(filename, 'w') as fp:
            fp.write(data)

        logger.info("[SAVED] %s to %s on %s" % (origin, destination, when))
        
        return filename, apikey
    
    return None, apikey


def fetch_booking(uri, body, apikey):
    return do_request('put', uri, body, apikey)


def follow_deeplinks(fetcher, element):
    filename, apikey, when, origin, destination, retries = element
    deep_executor = ThreadPoolExecutor(max_workers=20)
    
    logger.info("[FOLLOW] Flight from %s to %s on %s" % (when, origin, destination ))

    with open(filename) as fp:
        data = json.load(fp)

        # Save on DB
        data['_id'] = {'when': when, 'origin': origin, 'destination': destination}
        try:
            fetcher.itineraries.insert_one(data)
            logger.info("[INSERTED] Flight %r" % (data['_id']))
        except:
            logger.info("[DONE] Already exists flight %r" % (data['_id']))

        def fetch_itinerary(itinerary):
            id = itinerary[u'OutboundLegId']
            logger.info("[LOOKUP] Carrier of %s" % (id))

            # Is it on DB?
            if fetcher.carriers.find_one({'_id': id}) is None:
                details = itinerary[u'BookingDetailsLink']
                uri = 'http://partners.api.skyscanner.net' + details[u'Uri']
                data = details[u'Body']

                data = keep_polling(fetch_booking, 5, 10, apikey)(uri, data)
                if data is None:
                    logger.error("[ERROR] Could not follow deeplink (%d)" % (retries))

                    if retries < 3:
                        fetcher.pending_deep.put((filename, when, origin, destination, retries + 1))
                else:
                    data = json.loads(data)
                    data['_id'] = id
                    fetcher.carriers.insert_one(data)
                    logger.info("[INSERTED] Inserted carrier")
                    time.sleep(1)
            else:
                logger.info("[DONE] Already existing")
                                
        
        futures = [deep_executor.submit(fetch_itinerary, itinerary) for itinerary in data[u'Itineraries']]
        results = [f.result() for f in futures]
        


def wait_for(date, fmt, fetcher, wait=1):
    def worker(fetcher):
        self = threading.currentThread()
        wait_so_far = 0
        
        while True:
            if self.stop:
                logger.error('[STOP] Cancel thread')
                return
            
            if self.has_date:
                if get_date(self.fmt) == self.date:
                    self.has_date = False
                    fetcher.fetch()

            time.sleep(wait)
            wait_so_far += wait
            if wait_so_far >= 60 * 30:
                logger.info('[WAIT] +30m (%s .. %s)' % (get_date(self.fmt), self.date))
                wait_so_far = 0

    
    if wait_for.thread is None:
        wait_for.thread = threading.Thread(target=worker, args=(fetcher,))
        wait_for.thread.stop = False
    
    logger.info('\n[SCHEDULE] For %s at %s' % (date, get_date(fmt)))
    wait_for.thread.date = date
    wait_for.thread.fmt = fmt
    wait_for.thread.has_date = True
    if not wait_for.thread.isAlive():
        wait_for.thread.start()
    
wait_for.thread = None


# In[7]:

class Fetcher(object):
    HOUR = 60 * 60
    DAY = HOUR * 24
        
    def __init__(self, look_ahead_days, itineraries, start_time=None):
        start_time = int(time.time()) if start_time is None else int(start_time)
    
        self.LOOK_AHEAD = look_ahead_days * Fetcher.DAY
        self.TARGET_TIME = start_time + self.LOOK_AHEAD

        self.now = start_time
        self.start = self.now + self.LOOK_AHEAD
        self.target = self.TARGET_TIME
        self.flight_itineraries = itineraries
        self.stop = False
        
        self.pending_deep = Queue()
        self.client = pymongo.MongoClient('mongo-db')
        self.db = self.client.skyscanner
        self.carriers = self.db.carriers
        self.itineraries = self.db.itineraries
        
        self.fetch_executor = ThreadPoolExecutor(max_workers=len(api_keys_list))
        
        # Fix it up in case start_time is not now
        while self.now + self.LOOK_AHEAD + Fetcher.DAY - self.target >= self.LOOK_AHEAD:
            self.target += Fetcher.DAY
            logger.info('[SETUP] Skipping day')
            
    def fetch(self):
        if self.stop:
            return
        
        self.now = int(time.time())
        logger.info("-------------------------------------")
        logger.info("[UPDATE] Fetching day %d - %d" % ((self.now + self.LOOK_AHEAD + Fetcher.DAY - self.start) / Fetcher.DAY,
                                                        self.now))

        def push_fetch_save(origin, destination, ts, now):
            apikey = get_key()
            
            filename, apikey = fetch_and_save(origin, destination, get_date('%Y-%m-%d', ts), apikey)
            if filename is not None:
                element = (filename, apikey, get_date('%Y-%m-%d-%H', now), origin, destination, 0)
                follow_deeplinks(fetcher, element)

            release_key(apikey)
                            
        for ts in range(self.target, self.now + self.LOOK_AHEAD + Fetcher.DAY, Fetcher.DAY):
            for origin, destination in self.flight_itineraries:                
                self.fetch_executor.submit(push_fetch_save, origin, destination, ts, self.now)
                        
        if self.now + self.LOOK_AHEAD + Fetcher.DAY - self.target >= self.LOOK_AHEAD:
            self.target += Fetcher.DAY

        # Next day
        self.now += 6 * Fetcher.HOUR
        
        fmt = '%Y-%m-%d-%H'
        wait_for(get_date(fmt, self.now), fmt, self)


# In[ ]:

if __name__ == '__main__':
    http_pool = ProcessPoolExecutor(max_workers=5)

    def add_handler(logger, fh):
        logger.addHandler(fh)
        fh_fmt = logging.Formatter("%(asctime)s %(message)s")
        fh.setFormatter(fh_fmt)


    logger = logging.getLogger('SkyScanner')
    add_handler(logger, logging.FileHandler('skyscranner.log', 'a12'))
    #add_handler(logger, logging.StreamHandler())
    logger.setLevel(logging.INFO)

    def my_excepthook(excType, excValue, traceback, logger=logger):
        logger.error("Logging an uncaught exception",
                     exc_info=(excType, excValue, traceback))

    sys.excepthook = my_excepthook  
    
    api_keys_list = [
        'prtl6749387986743898559646983194',
        'py495888586774232134437415165965',
        'de995438234178656329029769192274',
        'cc379434454338361714672782744594',
        #'ilw01103795676959583463439374074', # ERROR
        #'ds4361952231231232435436345323' # ERROR
    ]

    if 'SKYSCANNER_API_KEY' in os.environ:
        api_keys_list.insert(0, os.environ['SKYSCANNER_API_KEY'])

    api_keys = Queue()
    for key in api_keys_list:
        api_keys.put(key)

    def get_key():
        global api_keys
        return api_keys.get()

    def release_key(key):
        global api_keys
        api_keys.put(key)
    
    
    destinations = (
        'LCY', 'LHR', 'LGW', 'LTN', 'SEN', 'STN', # LONDRES
        'CDG', 'ORY', 'BVA', # Paris
        'MAD', # Madrid
        'ATH', # Atenas
        'FCO', 'CIA', # Atenas
        'BRU', 'CRL', # Bruselas
        'BER', 'SXF', # Berlin
        'DME', 'SVO', # Moscu
        'SFO', # San Francisco
        'JFK', # Nueva York
        'PEK', # Pekin
        'EZE', # Buenos Aires
        'GIG', # Rio de Janeiro
        'DEL', # Delphi
    )

    itineraries = (('BCN', dest) for dest in destinations)
    fetcher = Fetcher(90, itineraries, start_time=1487923232)

    wait_for('2017-02-24-19', '%Y-%m-%d-%H', fetcher)
    while True:
        time.sleep(3600)

