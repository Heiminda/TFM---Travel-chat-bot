from datetime import datetime
import numpy as np
from time import sleep,time
from interruptingcow import timeout
from lxml import html,etree
import requests,re
import os,sys
import unicodecsv as csv
import argparse
from bs4 import BeautifulSoup
from random import choice, shuffle
import pymongo
import json


def main():

    #url='https://freevpn.ninja/free-proxy/json'
    #proxies=requests.get(url).json()

    user_agents = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/600.8.9 (KHTML, like Gecko) Version/8.0.8 Safari/600.8.9',
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36',
        'Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.1.3) Gecko/20090913 Firefox/3.5.3',
        'Mozilla/5.0 (Windows; U; Windows NT 6.1; en; rv:1.9.1.3) Gecko/20090824 Firefox/3.5.3 (.NET CLR 3.5.30729)',
        'Mozilla/5.0 (Windows; U; Windows NT 5.2; en-US; rv:1.9.1.3) Gecko/20090824 Firefox/3.5.3 (.NET CLR 3.5.30729)',
        'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.1) Gecko/20090718 Firefox/3.5.1',
        'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/532.1 (KHTML, like Gecko) Chrome/4.0.219.6 Safari/532.1',
        'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1; WOW64; Trident/4.0; SLCC2; .NET CLR 2.0.50727; InfoPath.2)'
        'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.0; Trident/4.0; SLCC1; .NET CLR 2.0.50727; .NET CLR 1.1.4322; .NET CLR 3.5.30729; .NET CLR 3.0.30729)',
        'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.2; Win64; x64; Trident/4.0)'
        'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; SV1; .NET CLR 2.0.50727; InfoPath.2)Mozilla/5.0 (Windows; U; MSIE 7.0; Windows NT 6.0; en-US)',
        'Mozilla/4.0 (compatible; MSIE 6.1; Windows XP)'
    ]

    preliminari_urls = ['https://www.tripadvisor.co.uk/Hotel_Review-g187497-d585139-Reviews-Hotel_Granados_83-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d877814-Reviews-Hotel_Murmuri_Barcelona-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d234572-Reviews-U232_Hotel-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d8875531-Reviews-Hotel_Upper_Diagonal-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d228466-Reviews-Crowne_Plaza_Barcelona_Fira_Center-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d260638-Reviews-Catalonia_Born-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d208596-Reviews-Hotel_Granvia-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d8800760-Reviews-Negresco_Princess_Hotel-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d206920-Reviews-NH_Collection_Barcelona_Podium-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d5416370-Reviews-Vincci_Gala_Barcelona-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d3373413-Reviews-Musik_Boutique_Hotel-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d7184002-Reviews-Hotel_Praktik_Vinoteca-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d228527-Reviews-Catalonia_Portal_de_l_Angel-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d291444-Reviews-Hotel_Omm-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d239542-Reviews-Hotel_Cram-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d239541-Reviews-Hostal_Grau-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d190615-Reviews-Hotel_Claris-Barcelona_Catalonia.html',
     'https://www.tripadvisor.co.uk/Hotel_Review-g187497-d232792-Reviews-Pol_Grace_Hotel-Barcelona_Catalonia.html']

    # Per obtenir urls hotels --> passar unes urls de test

    cities = ['Barcelona','London','Paris','Madrid','Athens, Greece','Rome','Brussels','Berlin','Moscou','San Francisco, United States', 'Beijing, China', 'New York City, United States','Buenos Aires, Argentina', 'Rio de Janeiro, Brazil', 'New Delhi, India']

    cont_collections = 0

    for city in cities[0:1]:

        # read json file of proxies
        with open('/Users/alexandrenixon/Documents/DS2/Chatbot/proxies.json') as data_file:
            proxies = json.load(data_file)

        headers,preliminari_proxy = test_proxy(user_agents,proxies,choice(preliminari_urls))

        checkin_date= datetime(2017, 9, 2)
        checkout_date= datetime(2017, 9, 3)

        # Info hotels + urls
        hotels,url_from_autocomplete = parse(city,checkin_date,checkout_date,headers,preliminari_proxy,sort=None)

        # Comencar iteracions amb proxy
        headers,proxy = test_proxy(user_agents,proxies,url = choice(hotels)['url'])

        # N de pagines de hotels
        n_hotel_pages = int(hotel_pages(url_from_autocomplete)[0])

        # Modificar url per loop amb paginacio
        url=hotel_url_pagination(url_from_autocomplete)

        # La demo nomes retorna 1 pagina de info, aqui agafo totes amb el camp 'url_from_autocomplete' que es retorna de funcio parse()
        urls, names = get_hotel_urls(url,headers, n_hotel_pages, user_agents,proxies,hotels)

        # Connection to Mongo DB
        try:
            conn=pymongo.MongoClient()
            print ""
            print "Connected successfully to MongoDB!"
            print ""
        except pymongo.errors.ConnectionFailure, e:
           print "Could not connect to MongoDB: %s" % e
        conn

        db = conn['TripAdvisor']

        barcelona = db.barcelona
        london = db.london
        paris = db.paris
        madrid = db.madrid
        athens = db.athens
        greece = db.greece
        rome = db.rome
        brussels = db.brussels
        berlin = db.berlin
        moscow = db.moscow
        sanfrancisco = db.sanfrancisco
        beijing = db.beijing
        newyork = db.newyork
        buenosaires = db.buenosaires
        riodejaneiro = db.riodejaneiro
        newdelhi = db.newdelhi


        collections = [barcelona, london, paris, madrid, athens, greece, rome, brussels, berlin, moscow, sanfrancisco, beijing, newyork, buenosaires, riodejaneiro, newdelhi]
        conn.close()
        ######################################## GET REVIEWS FROM EACH HOTEL AND INSERT IN MONGODB ########################################

        cont=0
        #XPATH_REVIEW = './/div[@class="wrap"]/div[contains(@class,"prw_rup")]//p[@class="partial_entry"]//text()'
        XPATH_REVIEW = './/div[@class="wrap"]/div[@class="prw_rup prw_common_html"][1]//p[@class="partial_entry"]//text()'
        XPATH_RATING = './/div[@class="wrap"]/div[@class="rating reviewItemInline"]/*[contains(@class, "ui_bubble_rating bubble_")]'


        for url,name in zip(urls,names):
            reviews = {'name':name,'comments':[], 'rating':[]}
            while True:
                try:
                    with timeout(7, exception=RuntimeError):
                        headers,proxy = test_proxy(user_agents,proxies,url = choice(hotels)['url'])
                except (RuntimeError,Exception) as e:
                    continue
                    pass
                break
            url_iter = review_url_pagination(url)
            print url_iter
            url="https://www.tripadvisor.co.uk" + url_iter
            index_pages = (url.format(i) for i in range(0, n_review_pages(url)*10, 10))
            iters=0
            for index in index_pages:
                intents = 0
                while True:
                    if intents == 10:
                        break
                    try:
                        with timeout(7, exception=RuntimeError):
                            result = requests.get(index,proxies = proxy, headers=headers).text
                    except (RuntimeError,Exception) as e:
                        intents += 1
                        sleep(20)
                        continue
                        pass
                    break
                parser = html.fromstring(result)
                reviews_page = parser.xpath(XPATH_REVIEW)
                ratings_page = parser.xpath(XPATH_RATING)
                ratings = [i.get('class')[-2] for i in ratings_page]
                #if len(reviews_page) > 0:
                #    print(index)
                #    print (len(reviews_page), len(ratings_page))
                #    if len(reviews_page)<20:
                #        for i in reviews_page:
                #            print i, '\n'
                #        for i in ratings:
                #            print i
                #    print "\n"
                #for i in ratings:
                #    print i
                #for i in reviews_page:
                #    print i

                reviews['comments'].extend(reviews_page)
                reviews['rating'].extend(ratings[:len(reviews_page)])
                del parser, result, reviews_page
                if cont==10:
                    while True:
                        try:
                            with timeout(7, exception=RuntimeError):
                                headers,proxy = test_proxy(user_agents,proxies,url = choice(hotels)['url'])
                        except (RuntimeError,Exception) as e:
                            continue
                            pass
                        cont=0
                        break
                cont+=1

            collections[cont_collections].insert_one(reviews)
            print 'Inserted comments of hotel:', name
            print ""
        cont_collections += 1

        ############################################################################################################


def test_proxy(user_agents,proxies,url):
    headers = {
        "Connection" : "close",  # another way to cover tracks
        "User-Agent" : choice(user_agents)}
    title=[]
    cont =0
    while title==[]:
        try:
            with timeout(5, exception=RuntimeError):
                while True:
                    proxy=choice(proxies)
                    #proxy = {"http" : ("http://" + proxy['ip'] + ":" + proxy['port']).encode("utf-8")}
                    XPATH_TITLE = '//*[@id="HEADING"]'
                    result = requests.get(url, proxies=proxy, headers=headers).text
                    parser = html.fromstring(result)
                    title = parser.xpath(XPATH_TITLE)
                    del parser, result
                    if title != []: break
        except (RuntimeError,Exception) as e:
            print 'Proxy error', e
            if cont == 10:
                sleep(30)
            if cont == 100:
                break
            cont += 1
    return headers, proxy

def hotel_pages(url_from_autocomplete):
    XPATH_N_HOTEL_PAGES = './/a[@class="pageNum last taLnk "]//text()'
    url= url_from_autocomplete
    result = requests.get(url).text
    parser = html.fromstring(result)
    n_hotel_pages = parser.xpath(XPATH_N_HOTEL_PAGES)
    del parser, result
    return n_hotel_pages

def n_review_pages(url):
    XPATH_N_HOTEL_PAGES = './/a[@class="pageNum taLnk"]//text()'
    result = requests.get(url).text
    parser = html.fromstring(result)
    npages = parser.xpath(XPATH_N_HOTEL_PAGES)
    if npages == []:
        npages = [1.0]
    del parser,result
    return int(npages[-1])

def hotel_url_pagination(url_from_autocomplete):
    p = re.compile("Hotels-[a-z][0-9]+-")
    for m in p.finditer(url_from_autocomplete):
        pos=m.end()
    dirc=list(url_from_autocomplete)
    dirc.insert(pos,'oa{}-')
    url="".join(dirc)
    return url

def review_url_pagination(url):
    p = re.compile("Reviews+-")
    for m in p.finditer(url):
        pos=m.end()
    dirc=list(url)
    dirc.insert(pos,'or{}-')
    url="".join(dirc)
    return url

def get_hotel_urls(url,headers, n_hotel_pages, user_agents, proxies, hotels):
    urls = []
    cont=0
    names = []
    proxy = choice(proxies)
    index_pages = (url.format(i) for i in range(0, n_hotel_pages*30, 30))
    XPATH_HOTEL_NAME = './/a[contains(@class,"property_title")]//text()'
    with requests.session() as s:
        for index in index_pages:
            try:
                with timeout(7, exception=RuntimeError):
                    r = s.get(index,proxies = proxy, headers=headers)
                    soup = BeautifulSoup(r.text, 'lxml')
                    url_list = [i.get('href') for i in soup.select('.property_title')]
                    parser = html.fromstring(r.text)
                    name_list = parser.xpath(XPATH_HOTEL_NAME)
                    urls.extend(url_list)
                    names.extend(name_list)
            except (RuntimeError,Exception) as e:
                print 'Proxy error', e
                proxy = choice(proxies)
    del parser,r,soup,url_list,name_list, index_pages, index
    s.close()
    return urls, names

def parse(locality,checkin_date,checkout_date,headers,preliminari_proxy,sort):
    checkIn = checkin_date.strftime("%Y/%m/%d")
    checkOut = checkout_date.strftime("%Y/%m/%d")
    print ""
    print "Scraper Inititated for Locality: %s"%locality
    # TA rendering the autocomplete list using this API
    #print "Finding search result page URL"
    geo_url = 'https://www.tripadvisor.co.uk/TypeAheadJson?action=API&startTime='+str(int(time()))+'&uiOrigin=GEOSCOPE&source=GEOSCOPE&interleaved=true&types=geo,theme_park&neighborhood_geos=true&link_type=hotel&details=true&max=12&injectNeighborhoods=true&query='+locality
    #print geo_url
    api_response  = requests.get(geo_url,headers=headers,proxies=preliminari_proxy).json()
    #getting the TA url for th equery from the autocomplete response
    url_from_autocomplete = "http://www.tripadvisor.co.uk"+api_response['results'][0]['url']
    print 'URL found %s'%url_from_autocomplete
    geo = api_response['results'][0]['value']
    #Formating date for writing to file

    date = checkin_date.strftime("%Y_%m_%d")+"_"+checkout_date.strftime("%Y_%m_%d")
    #form data to get the hotels list from TA for the selected date
    form_data ={
                    'adults': '2',
                    'dateBumped': 'NONE',
                    'displayedSortOrder':sort,
                    'geo': geo,
                    'hs': '',
                    'isFirstPageLoad': 'false',
                    'rad': '0',
                    'refineForm': 'true',
                    'requestingServlet': 'Hotels',
                    'rooms': '1',
                    'scid': 'null_coupon',
                    'searchAll': 'false',
                    'seen': '0',
                    'sequence': '7',
                    'o':"0",
                    'staydates': date,
                    'see_all_hotels': 'true'
    }
    #Referrer is necessary to get the correct response from TA if not provided they will redirect to home page

    headers = {
                            'Accept': 'text/javascript, text/html, application/xml, text/xml, */*',
                            'Accept-Encoding': 'gzip,deflate',
                            'Accept-Language': 'en-US,en;q=0.5',
                            'Cache-Control': 'no-cache',
                            'Connection': 'keep-alive',
                            'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
                            'Host': 'www.tripadvisor.com',
                            'Pragma': 'no-cache',
                            'Referer': url_from_autocomplete,
                            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:28.0) Gecko/20100101 Firefox/28.0',
                            'X-Requested-With': 'XMLHttpRequest'
                        }
    #print "Downloading search results page"
    page_response  = requests.post(url = "https://www.tripadvisor.co.uk/Hotels",data=form_data,headers = headers, proxies = preliminari_proxy).text
    #print "Parsing results "
    parser = html.fromstring(page_response)
    hotel_lists = parser.xpath('//div[contains(@class,"meta_listing")]')
    hotel_data = []
    hotel_links = []
    for hotel in hotel_lists:
        XPATH_HOTEL_LINK = './/div[@class="listing_title"]/a/@href'
        XPATH_REVIEWS  = './/span[@class="more review_count"]//text()'
        XPATH_RANK = './/div[@class="popRanking"]//text()'
        XPATH_RATING = './/div[@class="rating"]//span[contains(@class,"bubble_rating")]/@alt'
        XPATH_HOTEL_NAME = './/a[contains(@class,"property_title")]//text()'
        XPATH_HOTEL_FEATURES = './/a[contains(@class,"tag")]/text()'
        XPATH_HOTEL_PRICE = './/div[contains(@class,"price")]/text()'
        XPATH_VIEW_DEALS = './/div[contains(@id,"VIEW_ALL_DEALS")]/span/text()'
        XPATH_BOOKING_PROVIDER = './/div[contains(@class,"providerLogo")]/img/@alt'

        raw_booking_provider = hotel.xpath(XPATH_BOOKING_PROVIDER)
        raw_no_of_deals =  hotel.xpath(XPATH_VIEW_DEALS)
        raw_hotel_link = hotel.xpath(XPATH_HOTEL_LINK)
        raw_no_of_reviews = hotel.xpath(XPATH_REVIEWS)
        raw_rank = hotel.xpath(XPATH_RANK)
        raw_rating = hotel.xpath(XPATH_RATING)
        raw_hotel_name = hotel.xpath(XPATH_HOTEL_NAME)
        raw_hotel_features = hotel.xpath(XPATH_HOTEL_FEATURES)
        raw_hotel_price_per_night  = hotel.xpath(XPATH_HOTEL_PRICE)

        url = 'http://www.tripadvisor.co.uk'+raw_hotel_link[0] if raw_hotel_link else  None
        #reviews = re.findall('(\d+\,?\d+)',raw_no_of_reviews[0])[0].replace(',','') if raw_no_of_reviews else None
        rank = ''.join(raw_rank) if raw_rank else None
        rating = ''.join(raw_rating).replace(' of 5 bubbles','') if raw_rating else None
        name = ''.join(raw_hotel_name).strip() if raw_hotel_name else None
        hotel_features = ','.join(raw_hotel_features)
        price_per_night = ''.join(raw_hotel_price_per_night).encode('utf-8').replace('\n','') if raw_hotel_price_per_night else None
        no_of_deals=  re.sub('\D+','',''.join(raw_no_of_deals)) if raw_no_of_deals else None
        # no_of_deals = re.sub('\D+','',no_of_deals)
        booking_provider = ''.join(raw_booking_provider).strip() if raw_booking_provider else None

        data = {
                    'hotel_name':name,
                    'url':url,
                    'locality':locality,
                    #'reviews':reviews,
                    'tripadvisor_rating':rating,
                    'checkOut':checkOut,
                    'checkIn':checkIn,
                    'hotel_features':hotel_features,
                    'price_per_night':price_per_night,
                    'no_of_deals':no_of_deals,
                    'booking_provider':booking_provider

        }
        hotel_data.append(data)
        hotel_links.append(raw_hotel_link)

    return hotel_data,url_from_autocomplete

if __name__ == "__main__":
    main()
