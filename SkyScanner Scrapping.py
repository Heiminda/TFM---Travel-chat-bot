
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
from copy import deepcopy

COMMON_HTTP_ERRORS = [403, 404, 407, 410, 502, 598]
MULTITHREADING = True
WITH_MONGO = True
FORCE_STDOUT = False

if MULTITHREADING:
    from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
    from concurrent.futures import wait as wait_for_futures
    from concurrent.futures import as_completed
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

    def wait_for_futures(fs):
        pass

    def as_completed(fs):
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
        r = get_method(request_type)(url, data=payload, headers=headers, proxies={'http': proxy, 'https': proxy}, timeout=10)
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
                    logger.info("\t[WAIT] Waiting 1s for session to be created")
                    time.sleep(1) # Let session be created

                r_poll = parse_request(r, apikey, proxy)
                pending_session += 1

            if r_poll.status_code == 200:
                logger.info("[POOLED] Successfully pulled (Apikey: %s)" % (apikey,))
                return r_poll.text.encode('utf-8')

            if r_poll.status_code == 410:
                return 410

            current_try += 1
            if current_try < tries:
                #logger.error("\t[FAIL:%d] Reattempting in %d seconds (reason: %d, apikey: %s)" % (current_try, fail_wait, r_poll.status_code, apikey))

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

def fetch_and_save(origin, destination, when, apikey, proxy, tries=10, fail_wait=1):
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


def fetch_itinerary(carriers, origin, destination, itinerary, retry_lock, stop_signal, apikey, proxy):
    if stop_signal.isSet():
        return

    id = itinerary[u'OutboundLegId']
    logger.info("[LOOKUP] Carrier of %s" % (id))

    # Is it on DB?
    if not WITH_MONGO or carriers.find_one({'_id': id}) is None:
        details = itinerary[u'BookingDetailsLink']
        uri = 'http://partners.api.skyscanner.net' + details[u'Uri']
        body_details = details[u'Body']

        itinerary_data = keep_polling(fetch_booking, 10, 1, apikey, proxy, stop_signal)(uri, body_details)
        if type(itinerary_data) == int:
            if itinerary_data != -1:
                logger.error("[ERROR:%d] Could not follow deeplink (Apikey: %s)" % (itinerary_data, apikey))
                if (itinerary_data == 304 or (itinerary_data >= 400 and itinerary_data < 600)) and retry_lock.acquire(False):
                    stop_signal.set()
        else:
            if WITH_MONGO:
                try:
                    itinerary_data = json.loads(itinerary_data)
                    itinerary_data['_id'] = id
                    carriers.insert_one(itinerary_data)
                    logger.info("[INSERTED] Inserted carrier")

                except:
                    logger.error("[FATAL] Could not parse JSON of deeplink, from %s to %s on %s" % (origin, destination, when))
                    notify_mail("[SkyScanner] Could not parse JSON of deeplink, from %s to %s on %s" % (origin, destination, when), itinerary_data)
    else:
        logger.info("[DONE] Already existing")


def follow_deeplinks(fetcher, raw_data, origin, destination, ts, now, apikey, proxy):
    when = get_date('%Y-%m-%d-%H', ts)
    logger.error("[FOLLOW] Flight from %s to %s on %s (apikey=%s)" % (origin, destination, when, apikey))

    try:
        data = json.loads(raw_data)
    except:
        logger.error("[FATAL] Could not parse JSON, from %s to %s on %s" % (origin, destination, when))
        notify_mail("[SkyScanner] Could not parse JSON, from %s to %s on %s" % (origin, destination, when), raw_data)
        return fetcher.push_fetch_save(origin, destination, ts, now, apikey=apikey)

    # Save on DB
    data['_id'] = {
        'departure': get_date('%Y-%m-%d', ts),
        'date': get_date('%Y-%m-%d', now),
        'time': int(get_date('%H', now)),
        'origin': origin,
        'destination': destination
    }

    follow_carriers = True
    if WITH_MONGO:
        concat_id = {'_id.' + key: value for key, value in data['_id'].iteritems()}

        res = fetcher.itineraries.find_one(concat_id)
        if res is not None:
            logger.info("[DONE] Flight %r already exists" % (data['_id'],))
            return

        concat_id = {'_id.' + key: value for key, value in data['_id'].iteritems() if key != 'date' and key != 'time'}
        res = fetcher.itineraries.find_one(concat_id)
        follow_carriers = res is None
        logger.info("[EARLY_QUIT] Follow carriers for flight: %r" % (follow_carriers,))

    retry_lock = threading.Lock()
    stop_signal = threading.Event()

    if follow_carriers:
        deep_executor = ThreadPoolExecutor(max_workers=20)
        for itinerary in data[u'Itineraries']:
            deep_executor.submit(fetch_itinerary, fetcher.carriers, origin, destination, itinerary,
                                     retry_lock, stop_signal, apikey, proxy)

        deep_executor.shutdown(True)

    if retry_lock.acquire(False) and not stop_signal.isSet():
        try:
            fetcher.itineraries.insert_one(data)
            logger.info("[INSERTED] Flight %r" % (data['_id']))

        except Exception as e:
            logger.error("[UNK] Flight %s to %s on %s should not be already inserted" % (origin, destination, when))
            notify_mail("[SkyScanner] Already existing flight" + str(data['_id']), str(e) + "\n\n" + raw_data)
            return False
    else:
        # Retry
        return fetcher.push_fetch_save(origin, destination, ts, now, apikey=apikey)

    logger.info("[REACHED] Saved all carriers from %s to %s on %s" % (when, origin, destination ))
    return True


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
            logger.fatal('[INIT] Accumulate day')

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
                if data == 304 or (data >= 400 and data < 600):
                    # Proxy error, simply retry
                    self.push_fetch_save(origin, destination, ts, now, apikey=apikey)
                else:
                    logger.error('[ERROR:%d] Received null data' % (data,))
                    notify_mail('[SkyScanner] Unhandled HTTP Error: %d' % (data,), str((origin, destination)))

        except Exception as e:
            logger.error("Logging an uncaught exception", exc_info=True)

        if needs_key:
            release_key(apikey)

        return True

    def fetch(self):
        if self.stop:
            return

        self.now = int(time.time())
        logger.fatal("-------------------------------------")
        logger.fatal("[UPDATE] Fetching day %d (accumulate: %d) - %d" % ((self.now + Fetcher.DAY - self.start) / Fetcher.DAY,
                                                                         self.accumulate, self.now))

        notify_mail('[SkyScanner] Scrapping START - ' + get_date('%Y-%m-%d %H:%M', self.now), ':D')

        futures = []
        for day_offset in range(0, self.accumulate + 1):
            ts = self.now + self.LOOK_AHEAD - day_offset * Fetcher.DAY
            self.fetch_executor.submit(lambda d: logger.info("===== DOING DAY -%d =====" % (d,)), day_offset)

            for origin, destination in self.flight_itineraries:
                f = self.fetch_executor.submit(self.push_fetch_save, origin, destination, ts, self.now)
                futures.append(f)

        # Join
        total_futures = len(futures)
        done_futures = 0
        logger.info("[JOIN] Waiting for futures: %d" % (total_futures,))

        for ft in as_completed(futures):
            done_futures += 1
            logger.info("[FUTURE] Done %d/%d futures: %r" % (done_futures, total_futures, ft.result()))

            # TODO: Should not be needed
            if done_futures == total_futures:
                logger.info("[FUTURE] Done! Exiting wait")
                break

        while self.now < int(time.time()):
            logger.info("[SKIP] now+6h")
            self.now += 6 * Fetcher.HOUR

        fmt = '%Y-%m-%d-%H'
        if get_date('%Y-%m-%d', self.now + self.LOOK_AHEAD) != self.target:
            logger.info("[END] Moved target")
            self.accumulate = min(self.accumulate + 1, self.look_ahead_days)
            self.target = get_date('%Y-%m-%d', self.now + self.LOOK_AHEAD)

        logger.info('[END] Done scrapping for today! Next in: %s (accumulate: %d)' % (get_date(fmt, self.now), self.accumulate))
        wait_for(get_date(fmt, self.now), fmt, self)

        notify_mail('[SkyScanner] Scrapping ENDED - ' + get_date('%Y-%m-%d %H:%M', time.time()), ':D')


# In[ ]:
if __name__ == '__main__':
    http_pool = ProcessPoolExecutor(max_workers=5)

    def add_handler(logger, fh):
        logger.addHandler(fh)
        fh_fmt = logging.Formatter("%(asctime)s %(message)s")
        fh.setFormatter(fh_fmt)


    logger = logging.getLogger('SkyScanner')
    add_handler(logger, logging.FileHandler('skyscanner.log', 'a'))

    if not MULTITHREADING or FORCE_STDOUT:
        add_handler(logger, logging.StreamHandler())

    logger.setLevel(logging.INFO)

    def my_excepthook(original, exc_type, exc_value, exc_traceback, logger=logger):
        logger.error("Logging an uncaught exception",
                     exc_info=(exc_type, exc_value, exc_traceback))

        trace_msg = traceback.format_exception(exc_type, exc_value, exc_traceback)
        notify_mail('[SkyScanner] FATAL ERROR - ' + get_date('%Y-%m-%d %H:%M', time.time()), str(trace_msg))
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
    proxies_list = []

    def test_proxy(proxy):
        def _inner():
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
                r = requests.get('http://ip.jsontest.com/', headers=headers, proxies={'http': proxy, 'https': proxy}, timeout=10)
                obj = json.loads(r.text)
                return r.status_code == 200, r.status_code
            except Exception as e:
                return False, type(e)

        r = _inner()
        #logger.info("[PROXY] %s: %r" % (proxy, r))
        return r[0]

    def reload_proxies(start=0, acc=0):
        global proxies_list
        global proxies_lock
        try:
            proxy_req = requests.get('https://freevpn.ninja/free-proxy/json')
            proxy_json = json.loads(proxy_req.text)
            proxies_list_tmp = [p['proxy'] for p in proxy_json[start:start+10]]
            #logger.info("[PROXIES] Original size %d" % (len(proxies_list_tmp),))
            proxies_list_tmp = [p for p in proxies_list_tmp if test_proxy(p)] # Too slow... :(
            logger.info("[PROXIES] Cleaned size %d" % (len(proxies_list_tmp),))

            if len(proxies_list_tmp) + acc < 10:
                proxies_list_tmp += reload_proxies(start + 20, acc + len(proxies_list_tmp))

            if len(proxies_list_tmp) > 0 and start == 0:
                proxies_lock.acquire()
                proxies_list = cycle(proxies_list_tmp)
                proxies_lock.release()
        except Exception as e:
            print e
            proxies_list_tmp = []

        return proxies_list_tmp

    def next_proxy():
        global proxies_lock
        global proxies_list
        proxies_lock.acquire()
        proxy = next(proxies_list)
        proxies_lock.release()
        return proxy

    logger.info("[PROXIES] Loading initial list of proxies")
    proxies = reload_proxies()
    logger.info("[PROXIES] Initial size: %d" % (len(proxies),))

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
    # , start_time=1488249243, override_waitfor='2017-03-23-17'
    fetcher = Fetcher(90, itineraries, start_time=1488249243, override_waitfor='2017-03-31-13') #14

    while True:
        # Keep pooling proxies
        reload_proxies()
