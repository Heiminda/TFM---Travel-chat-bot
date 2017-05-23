import json
import pandas as pd
import numpy as np
import geocoder
from googlemaps import Client
from geopy.geocoders import Nominatim
import requests
from collections import Counter
import operator
import re

def main():

    trivago = pd.read_pickle('dataset.pkl')
    lat = trivago.loc[:,u'lat']
    lon = trivago.loc[:,u'lon']
    city = 'Barcelona'
    center_lat,center_lon = [41.392494, 2.169668]

    adressa = get_address(lat,lon)
    Barri = get_neighbourhood(adressa,' ' + city)
    barris_mes_turistics = turisme_barris(Barri)
    is_hotel_very_centric = hotel_very_centric(trivago,lat,lon,barris_mes_turistics,Barri,center_lat,center_lon)
    is_hotel_centric = hotel_centric(trivago,lat,lon,barris_mes_turistics,Barri,center_lat,center_lon)
    is_barri_very_centric = [i in [x[0] for x in barris_mes_turistics][:10] for i in Barri]
    Trivago_loc_info = pd.concat([trivago,pd.DataFrame(Barri, columns={'neighbourhood'}),pd.DataFrame(is_hotel_very_centric, columns={'is_hotel_very_centric'}),pd.DataFrame(is_hotel_centric, columns={'is_hotel_centric'}),pd.DataFrame(is_barri_very_centric, columns={'is_neighbourhood_very_centric'})],axis=1)

    pos_nans = np.argwhere(pd.isnull(Trivago_loc_info.neighbourhood)).ravel()
    nan_removal(df=Trivago_loc_info, positions=[pos_nans], column=['neighbourhood'], change_for='outskirt')
    Trivago_loc_info.to_csv('./Trivago_loc_info_2radious.csv', sep="\t", index=False, encoding = 'utf-8')


def get_address(lat,lon):
    print 'Obtaining adresses...'
    adressa=[]
    geolocator = Nominatim()
    for i in range(0,len(lat)):
        address = str(lat[i]) + ',' + str(lon[i])
        location = geolocator.geocode(address)
        adressa.append(location.address)
    print 'Completed'
    return adressa

def get_neighbourhood(adressa,city):
    i=0
    Barri=[]
    Districte=[]
    pat_dis = r'.*, (.*),' + city + '.*'
    pat_barri = r'.*, (.*), .*,' + city + '.*'
    for line in adressa:
        try:
            match = re.search(pat_dis, line)
            Districte.append(match.group(1))
            match2 = re.search(pat_barri, line)
            Barri.append(match2.group(1))
        except Exception:
            Districte.append(np.nan)
            Barri.append(np.nan)
    return Barri

def turisme_barris(Barri):
    # Numero de occurrences de cada element
    counts_barri = Counter(Barri)
    barris_mes_turistics = sorted(counts_barri.items(), key=operator.itemgetter(1))[::-1]
    delete_nans = pd.isnull(pd.Series([x[0] for x in barris_mes_turistics]))
    del barris_mes_turistics[np.where(delete_nans==True)[0][0]]
    return barris_mes_turistics

def hotel_very_centric(trivago,lat,lon,barris_mes_turistics,Barri,center_lat,center_lon):
    radius_meters = 1e3
    radius = radius_meters / 110.574e3
    is_very_centric = [None] * len(trivago)
    for lat, lon, cont in zip(trivago.loc[:,u'lat'],trivago.loc[:,u'lon'],range(len(trivago))):
        is_very_centric[cont] = (float(lat) - center_lat)**2 + (float(lon) - center_lon)**2 < radius**2
    return is_very_centric

def hotel_centric(trivago,lat,lon,barris_mes_turistics,Barri,center_lat,center_lon):
    radius_meters = 3e3
    radius_meters_very_centric = 1e3
    radius = radius_meters / 110.574e3
    small_radious = radius_meters_very_centric / 110.574e3
    is_centric = [None] * len(trivago)
    for lat, lon, cont in zip(trivago.loc[:,u'lat'],trivago.loc[:,u'lon'],range(len(trivago))):
        is_centric[cont] = (float(lat) - center_lat)**2 + (float(lon) - center_lon)**2 < radius**2 and (float(lat) - center_lat)**2 + (float(lon) - center_lon)**2 > small_radious**2
    return is_centric


def nan_removal(df,positions, column, change_for):
    for pos, col in zip(positions, column):
        df.set_value(pos,col,change_for);

if __name__ == "__main__":
    main()
