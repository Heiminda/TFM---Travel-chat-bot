import numpy as np
import pandas as pd

def main():

    # template
    #price = ['min', 'max']
    #specific_neighbourhood = ['Yes', 'No']
    #centricity = ['centric', 'dont_care', 'non_centric']

    # Example values
    price = [60,100]
    price_min, price_max = price
    specific_neighbourhood = 'No'
    neighbourhood = 'Raval'
    centricity = 'very centric'
    features = ['value_for_money','location']


    df = pd.read_csv('./trivago_extended.csv',sep='\t')

    # df filtered by price (all cases
    df = df[df['price'].between(price_min, price_max, inclusive = True)]

    # df filtered by features
    if features != []:
        df = filter_by_features(df,features)

    # df filtered by neighbourhood
    if specific_neighbourhood == 'Yes':
        df = df.loc[(df['neighbourhood'] == neighbourhood)]

    # df filtered by centric hotels
    if centricity == 'very centric':
        df = df.loc[(df['is_hotel_very_centric'] == True) & df['is_neighbourhood_very_centric'] == True]
    elif centricity == 'centric':
        df = df.loc[(df['is_hotel_centric'] == True)]
    elif centricity == 'non_centric':
        df = df.loc[(df['is_hotel_centric'] == False)]

    print df.hotel_name

def filter_by_features(df,features):
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


if __name__ == "__main__":
    main()
