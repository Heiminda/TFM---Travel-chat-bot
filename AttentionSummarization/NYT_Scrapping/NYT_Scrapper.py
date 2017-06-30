
# coding: utf-8

# In[49]:

import asyncio
import requests
import json
import pickle
from tqdm import tqdm as tqdm
from bs4 import BeautifulSoup


# In[27]:

async def do_request(url, method='get'):
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, getattr(requests, method), url)
    return await future


# In[52]:

async def nyt_page(number):
    url = 'https://www.nytimes.com/svc/collections/v1/publish/www.nytimes.com/section/aponline/news?q=&sort=newest&page={}&dom=www.nytimes.com&dedupe_hl=y'
    return await do_request(url.format(number))

async def main():
    news = []
    
    for page in tqdm(range(500)):
        resp = await nyt_page(page)
        resp = json.loads(resp.content)    
        news += resp['members']['items']
    
    return news


# In[53]:

loop = asyncio.get_event_loop()
news = loop.run_until_complete(main())
with open('news.pkl', 'wb') as fp:
    pickle.dump(news, fp)

# In[82]:

async def api_request(year, month, api_key):
    url = 'http://api.nytimes.com/svc/archive/v1/{}/{}.json?api-key={}'
    resp = await do_request(url.format(year, month, api_key))
    return json.loads(resp.content)

async def fetch_year(year, api_key):
    async def only_content(year, month, api_key):
        await asyncio.sleep(1)
        data = await api_request(year, month, api_key)
        try:
            return data['response']['docs']
        except Exception as e:
            print(data)
            return await only_content(year, month, api_key)
        
    news = [await only_content(year, month, api_key) for month in tqdm(range(1, 13), leave=False)]
    return news

async def fetch_many(api_key):
    api_news = [await fetch_year(year, api_key) for year in tqdm(range(2010, 2017))]
    api_news = sum(api_news, [])
    
    articles = [[news for news in api_news[k] if news['document_type'] == 'article'] for k in range(12)]
    articles = sum(articles, [])

    return articles


# In[83]:

loop = asyncio.get_event_loop()
articles = loop.run_until_complete(fetch_many('e48729d78b824b76a6eb151cd6e81ec7'))

with open('articles.pkl', 'wb') as fp:
    pickle.dump(articles, fp)

# In[ ]:



