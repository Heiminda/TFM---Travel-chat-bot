# coding: utf-8

from __future__ import division
import requests
import json
import numpy as np
from lxml import html
import Cookie
import time
import random
from interruptingcow import timeout
from datetime import datetime
import os

# printing in colors terminal
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class City:
    def __init__(self, name, path_id, request_id, geocode_lat, geocode_lng, cpt = None):
        self.name = name
        self.path_id = path_id
        self.cpt = cpt if cpt else None
        self.request_id = request_id
        self.geocode_lat = geocode_lat
        self.geocode_lng = geocode_lng

    def get_name(self):
        return self.name

    def get_pathid(self):
        return self.path_id

    def get_cpt(self):
        if self.cpt:
            return self.cpt
        else:
            return None

    def get_request_id(self):
        return self.request_id

    def get_geocode_lat(self):
        return self.geocode_lat

    def get_geocode_lng(self):
        return self.geocode_lng

# --------------------------------------
#   WEB HANDLERS
# --------------------------------------

def test_proxy(proxies, url):
    headers = {
        "Connection" : "close",  # another way to cover tracks
        "User-Agent" : 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36'}
    result = []
    success = False
    cont = 0
    while not success:
        try:
            with timeout(10, exception=RuntimeError):
                while True:
                    proxy = random.choice(proxies)
                    r = requests.get(url, proxies=proxy, headers=headers)
                    if r.status_code != 503: # successful
                        success = True
                        break
        except (RuntimeError,Exception) as e:
            print bcolors.FAIL +'\t\t\tTest_proxy() Error: ', e.args ,"." + bcolors.ENDC
        if cont == 100:
            break
        cont += 1
    return proxy

def get_proxies(path):
    with open(path) as f:
        proxies = json.load(f)
    return proxies

def parse_trivago_cookies(r):
    cookies = Cookie.SimpleCookie()
    cookies.load(r.headers['Set-Cookie'])
    return cookies

# execute this method only once
def get_trivago_cookies():
    headers = {
        'cache-control': 'max-age=0',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36'
    }

    r = requests.get("https://www.trivago.com", headers=headers)
    return parse_trivago_cookies(r)

def do_trivago_request(url, params, cookies, proxy_list, proxy, change_proxy):
    headers = {
        'cache-control': 'max-age=0',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36',
        'cookie': ''.join([name + '=' + morsel.coded_value for name, morsel in cookies.items()])
    }

    if change_proxy:
        proxy = test_proxy(proxy_list, "http://www.apple.com/es/")

    r = requests.get(url, params=params, headers=headers, proxies=proxy)

    if r.status_code == 200:
        return r, proxy
    else:
        print bcolors.WARNING + "\t\t\tRequest failed, retrying." + bcolors.ENDC
        time.sleep(1)
        return do_trivago_request(url, params, cookies, proxy_list, proxy, True)

def do_trivago_request_sess(url, session, params, proxy_list, proxy, change_proxy):
    headers = {
        'cache-control': 'max-age=0',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36'
    }

    if change_proxy:
        proxy = test_proxy(proxy_list, "http://www.apple.com/es/")

    r = requests.get(url, params=params, headers=headers, proxies = proxy)

    if r.status_code == 200 and len(r.text) > 10:
        return r, proxy
    else:
        print bcolors.WARNING + "\t\t\tRequest failed, retrying." + bcolors.ENDC
        time.sleep(1)
        return do_trivago_request_sess(url, session, params, proxy_list, proxy, True)

def poll_until_not_empty(url, params, cookies, proxy_list, proxy, count, proxy_count):

    # change proxy every 12 different requests
    if proxy_count % 12 == 0:
        print bcolors.WARNING + "\t\t\tChanging proxy." + bcolors.ENDC
        r,proxy = do_trivago_request(url, params, cookies, proxy_list, proxy, True)
    else:
        r,proxy = do_trivago_request(url, params, cookies, proxy_list, proxy, False)

    cookies = parse_trivago_cookies(r)

    xpath = "/html/body/div/main/div//ol"
    page = html.fromstring(r.text)
    element = page.xpath(xpath)[0]
    #print "getting prices"
    ids, prices = get_hotel_ids_prices(r.text)
    #print "got it"
    if len(ids) > 1 and prices and len(prices) > 1 and count <= 40:
        if '0' not in prices:
            return r
    #print "ok after if poll_until_not_empty"
    time.sleep(1)
    # print "\t poll_until_not_empty() Retrying in 1s"
    return poll_until_not_empty(url, params, cookies, proxy_list, proxy, count + 1, proxy_count)

# --------------------------------------
#   TRIVAGO DATA HANDLERS
# --------------------------------------

def getAttribute(data, attribute):
    res = None
    try:
        if attribute == "postal": res = data["accommodation"]["address"]["postalCode"]
        elif attribute == "street": res = data["accommodation"]["address"]["street"]
        elif attribute == "latitude": res = data["accommodation"]["centroid"]["latitude"]
        elif attribute == "longitude": res = data["accommodation"]["centroid"]["longitude"]
        elif attribute == "email": res = data["accommodation"]["contact"]["email"]
        elif attribute == "phone": res = data["accommodation"]["contact"]["phone"]
        elif attribute == "web": res = data["accommodation"]["contact"]["web"]
        elif attribute == "starcount": res = data["accommodation"]["hotelStarRating"]["starCount"]
        elif attribute == "is_premium": res = data["accommodation"]["isPremiumPartner"]
        elif attribute == "types": res = data["accommodation"]["types"]
        elif attribute == "name": res = data["accommodation"]["name"]
        elif attribute == "availableBeds": res = data["roomTypes"][0]["availableBeds"]
        elif attribute == "adequate": res = data["adequateFor"]
        elif attribute == "topfeatures":
            res = []
            for feat in data["amenities"]["topFeatures"]:
                res.append((feat["title"], feat["isAvailable"], feat["isFreeOfCharge"]))
        else:
            print "\t\t\t","!"*5,"Error get_hotel_info():",attribute,"does not exist in data."
        return res

    except Exception as e:
        print bcolors.WARNING + "\t\t\tError get_hotel_info(): while getting", attribute, ". Args:", e.args
        return None

def get_hotel_info(hotel_id, hotel_price, city):
    url = "https://www.trivago.es/api/v1/_cache/accommodation/"+hotel_id+"/complete-info.json"
    params = dict(requestId=city.get_request_id())

    response = requests.get(url, params=params)
    result = None

    if response.status_code == 200: # if successful
        try:
            data = json.loads(response.text)
        except Exception as e:
            print bcolors.FAIL + "\t\t\tError get_hotel_info(): while getting json data. Args:", e.args, "." + bcolors.ENDC
            return None

        result = get_ratings(hotel_id, city.get_request_id()) # get ratings

        result["hotel_id"] = hotel_id
        result["price"] = hotel_price
        result["postalCode"] = getAttribute(data, "postal")
        result["street"] = getAttribute(data, "street")
        result["latitude"] = getAttribute(data, "latitude")
        result["longitude"] = getAttribute(data, "longitude")
        result["email"] = getAttribute(data, "email")
        result["phone"] = getAttribute(data, "phone")
        result["web"] = getAttribute(data, "web")
        result["starCount"] = getAttribute(data, "starcount")
        result["isPremiumPartner"] = getAttribute(data, "is_premium")
        result["type"] = getAttribute(data, "types")
        result["name"] = getAttribute(data, "name")
        result["availableBeds"] = getAttribute(data, "availableBeds")
        result["adequateFor"] = getAttribute(data, "adequate")
        result["topFeatures"] = getAttribute(data, "topfeatures")

        return result
    else:
        print "Error get_hotel_info(): Status code not 200"
        return result

def get_hotel_ids_prices(html_source):
    st = ""

    if len(html_source) > 0:

        for line in html_source.splitlines():
            if line.startswith("appConfig.initialValues"):
                st = line
                break

        st = st[26:]
        st = st[:len(st)-1]

        hotel_ids = []
        hotel_prices = []
        try:
            json_st = json.loads(st)

            hotel_ids = json_st["metadata"]["gtm"]["variables"]["itemIds"].split(",")
            hotel_prices = json_st["metadata"]["gtm"]["variables"]["itemRates"].split(",")

            return hotel_ids, hotel_prices

        except Exception:
            print bcolors.FAIL + "\t\t\tError get_hotel_ids_prices(): JSON object parsing failed." + bcolors.ENDC
            return hotel_ids, hotel_prices
    else:
        print "Error get_hotel_ids_prices(): No html source."
        return None

def get_rating_attributes(data, attribute):
    res = None
    try:
        if attribute == "partner_review_count":
            res =  data["ratingSummary"]["partnerReviewCount"]
        elif attribute == "review_partners":
            res = []
            for review in data["ratingSummary"]["reviewPartners"]:
                name = review["name"]
                partner_id = review["id"]
                rating_perc = review["ratingPercentage"]
                res.append((name, partner_id, rating_perc))
        elif attribute == "total_rating":
            data["ratingSummary"]["reviewRating"]["percentage"]
        elif attribute == "ratings":
            res = []
            for rating in data["ratingSummary"]["ratingAspects"]:
                res.append((rating["percentage"],rating["type"]))
        elif attribute == "quality_test":
            res = data["ratingSummary"]["hasQualityTests"]

        else:
            print "Error get_hotel_info():",attribute,"does not exist in data."
        return res

    except Exception as e:
        print bcolors.WARNING + "\t\t\tError get_ratings(): while getting", attribute, ". Args:", e.args, "." + bcolors.ENDC
        return None

def get_ratings(hotel_id, city_request_id):
    url = "https://www.trivago.es/api/v1/_cache/accommodation/" + hotel_id + "/web34591/ratings.json?"
    params = dict(requestId="v11_03_1_ae_es_ES_ES")

    response = requests.get(url, params=params)
    result = None

    if response.status_code == 200: # if successful response
        try:
            data = json.loads(response.text)
        except Exception as e:
            print bcolors.FAIL + "\t\t\tError get_ratings(): JSON object parsing failed." + bcolors.ENDC
            return None

        partnerReviewCount = get_rating_attributes(data,"partner_review_count")
        reviewPartners = get_rating_attributes(data,"review_partners")
        hotel_total_rating = get_rating_attributes(data,"total_rating")
        has_quality_test = get_rating_attributes(data,"quality_test")
        ratings = get_rating_attributes(data,"ratings")

        result = {"partnerReviewCount":partnerReviewCount,
                  "reviewPartners":reviewPartners,
                  "hotel_total_rating":hotel_total_rating,
                  "has_quality_test":has_quality_test,
                  "ratings":ratings}

        return result
    else:
        print "\t\t\tError get_ratings(): Status code not 200"
        return result


# --------------------------------------
#   MAIN PROCEDURE
# --------------------------------------

def define_params(path_id, room_type, offset, include_all, geocode_lat, geocode_lng, cpt = ""):
    return {"iPathId": path_id,
              "bDispMoreFilter":"false",
              "aDateRange[arr]":"2017-04-02",
              "aDateRange[dep]":"2017-04-03",
              "aCategoryRange":"0%2C1%2C2%2C3%2C4%2C5",
              "iRoomType":str(room_type), # 1 = individual, 7 = double
              "sOrderBy":"relevance desc",
              "aPartner":"",
              "aOverallLiking":"1%2C2%2C3%2C4%2C5",
              "iOffset": str(offset), # change search page
              "iLimit":"25",
              "iIncludeAll": str(include_all), # include both available and not available hotels
              "bTopDealsOnly":"false",
              "iViewType":"0",
              "aPriceRange[to]":"0",
              "aPriceRange[from]":"0",
              "aGeoCode[lng]":geocode_lng,
              "aGeoCode[lat]":geocode_lat,
              "bIsSeoPage":"false",
              "aHotelTestClassifier":"",
              "bSharedRooms":"false",
              "bIsSitemap":"false",
              "rp":"",
              "cpt": cpt if cpt != "" else "",
              "iFilterTab":"0"}

def scrape(city, room_type, include_all):

    url = "https://www.trivago.es/"

    # Temporal Storage
    # offset_page_index = 0 # search_page reminder
    # data_page_reminder  = open("trivagoReminder_%s_%s_%s_%s_%s.txt" % (city.get_name(), city.get_pathid(), room_type, include_all, datetime.now().strftime("%Y-%m-%d_%H:%M:%S")), "w")

    if not os.path.exists("trivago_data/%s" % city.get_name()):
        os.makedirs("trivago_data/%s" % city.get_name())

    data_file = open("trivago_data/%s/trivago_%s_%s_%s_%s_%s.txt" % (city.get_name(), city.get_name(), city.get_pathid(), room_type, include_all, datetime.now().strftime("%Y-%m-%d_%H:%M:%S")), "w")

    print bcolors.OKBLUE + "INITIALIZING SCRAPER"
    print "\tParameters:"
    print "\t\tCity:", city.get_name()
    print "\t\tPath_id:", city.get_pathid()
    print "\t\tRoom_type:", "Individual" if room_type == "1" else "Double"
    print "\t\tInclude_all:", "Yes" if include_all == 1 else "No"
    print "\n" + bcolors.ENDC

    # set of search pages
    offsets = [i for i in range(0,475,25)]

    # get cookies only once
    print "\tGetting cookies."
    cookies = get_trivago_cookies()
    print bcolors.OKGREEN + "\tCookies ok." + bcolors.ENDC

    # test and get workable proxy
    print "\tTesting and getting workable proxy..."
    proxy_list = get_proxies("proxies.json")
    proxy = test_proxy(proxy_list, "http://www.apple.com/es/")
    print bcolors.OKGREEN +"\tGot proxy." + bcolors.ENDC
    proxy_count = 1

    print "\tStarting to scrape."

    try:
        for search_page in offsets:
            print "\t\tSearch page:", search_page / 25 , "."

            if city.get_cpt() is not None:
                params = define_params(city.get_pathid(), room_type, search_page, include_all, city.get_geocode_lat(), city.get_geocode_lng(), city.get_cpt())
            else:
                params = define_params(city.get_pathid(), room_type, search_page, include_all, city.get_geocode_lat(), city.get_geocode_lng(), city.get_cpt())

            print "\t\tDoing request..."
            # get trivago response
            response = poll_until_not_empty(url, params, cookies, proxy_list, proxy, 0, proxy_count)
            print bcolors.OKGREEN + "\t\tGot response, status code:",response.status_code,"." + bcolors.ENDC
            # get html source
            html_source = response.text
            print "\t\tGetting hotel_ids and prices..."
            # get data
            hotel_ids, hotel_prices = get_hotel_ids_prices(html_source)
            num_hotels = len(hotel_ids)
            print bcolors.OKGREEN +"\t\tObtained",num_hotels,"hotels to scrape." + bcolors.ENDC
            print "\t\tStarting to scrape detailed hotel information..."

            for i,hotel_id in enumerate(hotel_ids):
                print "\t\t\tProcessing Hotel id:", hotel_id,". Number",i+1,"out of",num_hotels,"..."
                info = get_hotel_info(hotel_id, hotel_prices[i],city)
                print bcolors.OKGREEN +"\t\t\tGot detailed information." + bcolors.ENDC
                # wait a few seconds
                print "\t\t\tWaiting..."
                time.sleep(2)
                # now update db
                print "\t\t\tWriting to file..."
                json.dump(info, data_file)
                data_file.write("\n")
                print bcolors.OKGREEN +"\t\t\tFile updated." + bcolors.ENDC
                print "\n"
                proxy_count += 1
    except Exception as e:
        print bcolors.FAIL + "\t\t\tMain scraper failed. Error:", e ,"." + bcolors.ENDC
    finally:
        data_file.close()
        print "SCRAPER FAILED. Quitting..."
        return None

        # TODO:
        # mongodb
        # try catch

    data_file.close()
    print "SCRAPING  ", city.get_name(), " COMPLETED SUCCESSFULLY."
    return None

if __name__ == '__main__':

    city_names = ['London','Paris','Madrid','Athens, Greece','Rome','Brussels','Berlin','Moscou','San Francisco, United States', 'Beijing, China',
        'New York City, United States','Buenos Aires, Argentina', 'Rio de Janeiro, Brazil', 'New Delhi, India']

    London = City(name="London", path_id="38715", request_id = "v11_03_3_ai_es_ES_ES", geocode_lat="51.507359", geocode_lng="-0.127668", cpt = "3871503")

    cities = [London]
    rooms_types = ["1","7"]

    for i,city in enumerate(cities):
        for room_type in rooms_types:
            scrape(city, room_type, 1)
