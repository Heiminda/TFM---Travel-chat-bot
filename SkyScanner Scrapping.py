
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
import traceback
import smtplib
import email.utils
from email.mime.text import MIMEText
from itertools import cycle
from Queue import Queue

COMMON_HTTP_ERRORS = [403, 404, 407, 410, 502, 598]
MULTITHREADING = True
WITH_MONGO = True

if MULTITHREADING:
    from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
else:
    class DummyFuture:
        def __init__(self, res):
            self.res = res

        def result(self):
            return self.res

    class ThreadPoolExecutor(object):
        def __init__(self, *args, **kwargs):
            pass

        def submit(self, func, *args, **kwargs):
            return DummyFuture(func(*args, **kwargs))

        def shutdown(self, wait=True):
            pass

    ProcessPoolExecutor = ThreadPoolExecutor

def notify_mail(subject, body):
    sender = 'manuelsarmientodatactions@gmail.com'
    to = 'gpascualg93@gmail.com'
    msg = MIMEText(body)
    msg['To'] = email.utils.formataddr(('Recipient', to))
    msg['From'] = email.utils.formataddr(('Author', sender))
    msg['Subject'] = subject

    # Send the message via our own SMTP server, but don't include the 
    # envelope header. 
    server = smtplib.SMTP('smtp.gmail.com',587) 
    server.ehlo() 
    server.starttls()     
    server.login("manuelsarmientodatactions@gmail.com", "Datactions") 
    try:
        server.sendmail(sender, [to], msg.as_string()) 
    finally:
        server.quit()

# In[4]:

def do_request(request_type, url, data, apikey, proxy):
    logger.info('[REQ:%s] %s\n\tApikey: %s (Proxy: %s)' % (request_type, url, apikey, proxy))
    return http_pool.submit(do_request_imp, request_type, url, data, apikey, proxy).result()
    #return do_request_imp(request_type, url, data, apikey, proxy)

class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)

def do_request_imp(request_type, url, data, apikey, proxy):
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

    try:
        r = get_method(request_type)(url, data=payload, headers=headers, proxies={'http': proxy, 'https': proxy}, timeout=5)
    except Exception as e:
        return Struct(status_code=598, exception=e)

    return r


def parse_request(r, apikey, proxy):
    if r.status_code == 201:
        return do_request('get', r.headers['Location'], {}, apikey, proxy)

    return r


# In[5]:

def fetch_data(origin, destination, when, apikey, proxy):
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

    return do_request('post', 'http://partners.api.skyscanner.net/apiservices/pricing/v1.0', data, apikey, proxy)

def keep_polling(func, tries, fail_wait, apikey, proxy, stop_signal=None):
    def _inner(*args, **kwargs):
        current_try = 0

        while current_try < tries:
            r = func(*args, apikey=apikey, proxy=proxy, **kwargs)

            r_poll = None
            pending_session = 0
            while (r_poll == None or r_poll.status_code == 304) and pending_session < 5:
                if stop_signal is not None:
                    if stop_signal.isSet():
                        return -1

                if pending_session > 0:
                    logger.info("\t[WAIT] Waiting %ds for session to be created" % (pending_session * 2 + 1))
                    time.sleep((pending_session - 1) * 2 + 1) # Let session be created

                r_poll = parse_request(r, apikey, proxy)
                pending_session += 1

            if r_poll.status_code == 200:
                logger.info("[POOLED] Successfully pulled (Apikey: %s)" % (apikey,))
                return r_poll.text.encode('utf-8')

            if r_poll.status_code == 410:
                return 410

            current_try += 1
            if current_try < tries:
                logger.error("\t[FAIL:%d] Reattempting in %d seconds (reason: %d, apikey: %s)" % (current_try, fail_wait, r_poll.status_code, apikey))
     
                if r_poll.status_code == 429: # Too many requests
                    time.sleep(fail_wait)
                else:
                    time.sleep(0.5)

        return r_poll.status_code

    return _inner



# In[6]:

def get_date(fmt, ts=None):
    ts = int(time.time()) if ts is None else int(ts)
    date = datetime.datetime.fromtimestamp(ts).strftime(fmt)
    return date

def parse_date(fmt, date):
    ts = time.mktime(datetime.datetime.strptime(date, fmt).timetuple())
    return ts

def fetch_and_save(origin, destination, when, apikey, proxy, tries=7, fail_wait=10):
    logger.info("[DO] %s to %s on %s" % (origin, destination, when))

    date = get_date('%Y-%m-%d-%H')
    filename = '%s_%s_%s_%s.json' % (origin, destination, date, when)
    filename = os.path.join('flights-data', filename)

    try:
        os.makedirs('flights-data')
    except:
        pass

    data = keep_polling(fetch_data, tries, fail_wait, apikey, proxy)(origin, destination, when)
    if type(data) == int:
        logger.error("[ERROR:%d] %s to %s on %s, apikey=%s" % (data, origin, destination, when, apikey))
    else:
        logger.info("[SAVED] %s to %s on %s" % (origin, destination, when))

    # Data might be int, which means error code
    return data, apikey


def fetch_booking(uri, body, apikey, proxy):
    return do_request('put', uri, body, apikey, proxy)


def follow_deeplinks(fetcher, raw_data, origin, destination, ts, now, apikey, proxy):
    when = get_date('%Y-%m-%d-%H', ts)
    deep_executor = ThreadPoolExecutor(max_workers=20)
    logger.info("[FOLLOW] Flight from %s to %s on %s" % (origin, destination, when))

    try:
        data = json.loads(raw_data)
    except:
        logger.error("[FATAL] Could not parse JSON, from %s to %s on %s" % (origin, destination, when))
        notify_mail("[SkyScanner] Could not parse JSON, from %s to %s on %s" % (origin, destination, when), data)
        fetcher.push_fetch_save(origin, destination, ts, now, apikey=apikey)
        return

    # Save on DB
    data['_id'] = {
        'departure': get_date('%Y-%m-%d', ts),
        'date': get_date('%Y-%m-%d', now),
        'time': int(get_date('%H', now)), 
        'origin': origin, 
        'destination': destination
    }
    flight_data = data

    if WITH_MONGO:
        if fetcher.itineraries.find_one(flight_data) is not None:
            logger.info("[DONE] Flight %r already exists" % (data['_id'],))
            return

    def fetch_itinerary(itinerary, futures, retry_lock, stop_signal):
        if stop_signal.isSet():
            return

        id = itinerary[u'OutboundLegId']
        logger.info("[LOOKUP] Carrier of %s" % (id))

        # Is it on DB?
        if not WITH_MONGO or fetcher.carriers.find_one({'_id': id}) is None:
            details = itinerary[u'BookingDetailsLink']
            uri = 'http://partners.api.skyscanner.net' + details[u'Uri']
            body_details = details[u'Body']

            itinerary_data = keep_polling(fetch_booking, 7, 10, apikey, proxy, stop_signal)(uri, body_details)
            if type(itinerary_data) == int:
                if itinerary_data != -1:
                    logger.error("[ERROR:%d] Could not follow deeplink (Apikey: %s)" % (itinerary_data, apikey))
                    if itinerary_data >= 400 and itinerary_data < 600 and retry_lock.acquire(False):
                        stop_signal.set()
                        fetcher.push_fetch_save(origin, destination, ts, now, apikey=apikey)
                        for f in futures:
                            f.cancel()
            else:
                if WITH_MONGO:
                    try:
                        itinerary_data = json.loads(itinerary_data)
                        itinerary_data['_id'] = id
                        fetcher.carriers.insert_one(itinerary_data)
                        logger.info("[INSERTED] Inserted carrier")

                    except:
                        logger.error("[FATAL] Could not parse JSON of deeplink, from %s to %s on %s" % (origin, destination, when))
                        notify_mail("[SkyScanner] Could not parse JSON of deeplink, from %s to %s on %s" % (origin, destination, when), itinerary_data)
        else:
            logger.info("[DONE] Already existing")


    futures = []
    retry_lock = threading.Lock()
    stop_signal = threading.Event()
    for itinerary in data[u'Itineraries']:
        deep_executor.submit(fetch_itinerary, itinerary, futures, retry_lock, stop_signal)

    deep_executor.shutdown(True)

    if retry_lock.acquire(False) and not stop_signal.isSet():
        try:
            fetcher.itineraries.insert_one(flight_data)
            logger.info("[INSERTED] Flight %r" % (flight_data['_id']))
        except Exception as e:
            logger.info("[UNK] Flight should not be already inserted")
            notify_mail("[SkyScanner] Already existing flight" + str(flight_data['_id']), str(e) + "\n\n" + raw_data)

    logger.info("[REACHED] Saved all carriers from %s to %s on %s" % (when, origin, destination ))


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

    def __init__(self, look_ahead_days, itineraries, start_time=None, override_waitfor=None):
        start_time = int(time.time()) if start_time is None else int(start_time)

        self.look_ahead_days = look_ahead_days
        self.LOOK_AHEAD = look_ahead_days * Fetcher.DAY

        self.now = start_time
        self.start = start_time
        self.accumulate = 0
        self.flight_itineraries = itineraries
        self.stop = False

        self.client = pymongo.MongoClient('mongo-db')
        self.db = self.client.skyscanner
        self.carriers = self.db.carriers
        self.itineraries = self.db.itineraries

        self.fetch_executor = ThreadPoolExecutor(max_workers=len(api_keys_list))

        current_date = int(time.time())
        while get_date('%Y-%m-%d', self.now) != get_date('%Y-%m-%d', current_date):
            self.accumulate = min(self.accumulate + 1, self.look_ahead_days)
            self.now += Fetcher.DAY
            logger.info('[INIT] Accumulate day')

        self.target = get_date('%Y-%m-%d', self.now + self.LOOK_AHEAD)
       
        if override_waitfor is None:
            wait_for(get_date('%Y-%m-%d-%H', self.now), '%Y-%m-%d-%H', self)
        else:
            wait_for(override_waitfor, '%Y-%m-%d-%H', self)


    def push_fetch_save(self, origin, destination, ts, now, apikey=None):
        needs_key = apikey is None
        if needs_key:
            apikey = get_key()

        proxy = next_proxy()

        try:
            data, apikey = fetch_and_save(origin, destination, get_date('%Y-%m-%d', ts), apikey, proxy)
            if not type(data) == int:
                follow_deeplinks(fetcher, data, origin, destination, ts, now, apikey, proxy)
            else:
                if data >= 400 and data < 600:
                    # Proxy error, simply retry
                    self.push_fetch_save(origin, destination, ts, now, apikey=apikey)
                else:
                    logger.error('[ERROR:%d] Received null data' % (data,))
                    notify_mail('[SkyScanner] Unhandled HTTP Error: %d' % (data,), str((origin, destination)))

        except Exception as e:
            logger.error("Logging an uncaught exception", exc_info=True)

        if needs_key:
            release_key(apikey)

    def fetch(self):
        if self.stop:
            return

        self.now = int(time.time())
        logger.info("-------------------------------------")
        logger.info("[UPDATE] Fetching day %d (accumulate: %d) - %d" % ((self.now + Fetcher.DAY - self.start) / Fetcher.DAY,
                                                                         self.accumulate, self.now))

        notify_mail('[SkyScanner] Scrapping START - ' + get_date('%Y-%m-%d %H:%M', self.now), ':D')

        futures = []
        for day_offset in range(0, self.accumulate + 1):
            logger.info("===== DAY -%d =====" % (day_offset,))
            ts = self.now + self.LOOK_AHEAD - day_offset * Fetcher.DAY
            for origin, destination in self.flight_itineraries:
                f = self.fetch_executor.submit(self.push_fetch_save, origin, destination, ts, self.now)
                futures.append(f)

        self.now += 6 * Fetcher.HOUR

        if get_date('%Y-%m-%d', self.now + self.LOOK_AHEAD) != self.target:
            self.accumulate = min(self.accumulate + 1, self.look_ahead_days)
            self.target = get_date('%Y-%m-%d', self.now + self.LOOK_AHEAD)

        fmt = '%Y-%m-%d-%H'
        wait_for(get_date(fmt, self.now), fmt, self)

        # Join
        results = [f.result() for f in futures]
        logger.info('[END] Done scrapping for today! Next in: %s (accumulate: %d)' % (get_date(fmt, self.now), self.accumulate))

        notify_mail('[SkyScanner] Scrapping ENDED - ' + get_date('%Y-%m-%d %H:%M', time.time()), ':D')


# In[ ]:

if __name__ == '__main__':
    http_pool = ProcessPoolExecutor(max_workers=5)

    def add_handler(logger, fh):
        logger.addHandler(fh)
        fh_fmt = logging.Formatter("%(asctime)s %(message)s")
        fh.setFormatter(fh_fmt)


    logger = logging.getLogger('SkyScanner')
    add_handler(logger, logging.FileHandler('skyscranner.log', 'a'))

    if not MULTITHREADING:
        add_handler(logger, logging.StreamHandler())

    logger.setLevel(logging.INFO)

    def my_excepthook(original, exc_type, exc_value, exc_traceback, logger=logger):
        logger.error("Logging an uncaught exception",
                     exc_info=(exc_type, exc_value, exc_traceback))

        trace_msg = traceback.format_exception(exc_type, exc_value, exc_traceback)
        notify_mail('[SkyScanner] FATAL ERROR - ' + get_date('%Y-%m-%d %H:%M', self.now), str(trace_msg))
        original_excepthook(exc_type, exc_value, exc_traceback)

    original_excepthook = sys.excepthook
    sys.excepthook = lambda *args, **kwargs: my_excepthook(original_excepthook, *args, **kwargs)

    api_keys_list = [
        'prtl6749387986743898559646983194',
        'py495888586774232134437415165965',
        'de995438234178656329029769192274',
        'de187392941311932513127356346821',
        'cc379434454338361714672782744594',
        #'ilw01103795676959583463439374074', # ERROR
        #'ds4361952231231232435436345323' # ERROR,
    ]

    if 'SKYSCANNER_API_KEY' in os.environ:
        api_keys_list.insert(0, os.environ['SKYSCANNER_API_KEY'])

    api_keys = Queue()
    for key in api_keys_list:
        api_keys.put(key)

    def get_key():
        global api_keys
        key = api_keys.get()
        logger.info("<<< Get key: %s" % (key,))
        return key

    def release_key(key):
        global api_keys
        api_keys.put(key)
        logger.info(">>> Put key: %s" % (key,))


    proxies_lock = threading.Lock()
    proxies_list = cycle([
        "35.185.60.220:80", "198.50.237.204:8080", "177.54.146.249:8080",
        "51.15.143.172:8000", "103.14.8.239:8080", "144.217.156.166:8080",
        "200.229.193.147:3128", "5.196.67.182:3128", "104.196.6.191:80",
        "36.73.167.246:81", "93.188.167.171:8080", "201.16.147.193:80",
        "45.55.15.48:3128", "158.69.193.152:1080", "158.69.70.238:8080",
        "158.69.82.180:8080", "94.177.198.7:3128", "104.196.186.68:80",
        "200.229.202.139:8080", "62.151.183.58:80"])

    def test_proxy(proxy):
        def _inner():
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
                r = requests.get('http://proxy.tekbreak.com/best/json', headers=headers, proxies={'http': proxy, 'https': proxy}, timeout=5)
                obj = json.loads(r.text)
                return r.status_code == 200, r.status_code
            except Exception as e:
                return False, e
        r = _inner()
        #logger.info("[PROXY] %s: %r" % (proxy, r))
        return r[0]

    def reload_proxies():
        global proxies_list
        global proxies_lock
        try:
            proxy_req = requests.get('http://proxy.tekbreak.com/100/json')
            proxy_json = json.loads(proxy_req.text)
            proxies_list_tmp = [p['ip'] + ':' + p['port'] for p in proxy_json]
            logger.info("[PROXIES] Original size %d" % (len(proxies_list_tmp),))
            proxies_list_tmp = [p for p in proxies_list_tmp if test_proxy(p)] # Too slow... :(
            logger.info("[PROXIES] Cleaned size %d" % (len(proxies_list_tmp),))

            proxies_lock.acquire()
            proxies_list = cycle(proxies_list_tmp)
            proxies_lock.release()
        except Exception as e:
            pass
    
    def next_proxy():
        global proxies_lock
        global proxies_list
        proxies_lock.acquire()
        proxy = next(proxies_list)
        proxies_lock.release()
        return proxy

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

    itineraries = [('BCN', dest) for dest in destinations]
    fetcher = Fetcher(90, itineraries, start_time=1488249243, override_waitfor='2017-03-07-17') #14
    #fetcher = Fetcher(90, itineraries)

#    filename, api = fetch_and_save('BCN', 'PMI', '2017-03-24', get_key())
#    print "DONE A"
#    follow_deeplinks(fetcher, (filename, api, '2017-03-24-02', 'BCN', 'PMI'))
#    print "DONE B"
#    release_key(api)

    while True:
        # Keep pooling proxies
        reload_proxies()

