import config
import requests_cache
import sys


from bs4 import BeautifulSoup
from mysql.connector import connect, Error
from urllib.parse import urldefrag, urljoin


LIMIT = 12 # how many items to scrape in one go, at most


if __name__ == '__main__':
    with connect(host=config.db_host, user=config.db_user,
            password=config.db_pass, database=config.db_name) \
            as connection, connection.cursor() as cursor:
        query = 'SELECT link FROM vffk';
        cursor.execute(query)
        links = set(link for (link,) in cursor.fetchall())
        session = requests_cache.CachedSession('vffk', backend='memory')
        index_url = 'https://www.titanic-magazin.de/fachmann/archiv/'
        index_res = session.get(index_url)
        index_soup = BeautifulSoup(index_res.content, 'html.parser')
        records = []
        for a in reversed(index_soup.select('div#briefe > nav > map > ul > li > ul > li > a')):
            link = urljoin(index_url, a.get('href'))
            if link in links:
                continue
            print(f'INFO: scraping {link}', file=sys.stderr)
            month_url, frag = urldefrag(link)
            month_res = session.get(month_url)
            month_soup = BeautifulSoup(month_res.content, 'html.parser')
            div = month_soup.find('div', id=frag)
            if not div:
                print(f'WARNING: #{frag} not found', file=sys.stderr)
                continue
            children = tuple(div.children)
            title = children[0].get_text()
            text = ''
            for child in children[1:-1]:
                text += str(child)
            author = children[-1].get_text().strip()
            records.append({'link': link, 'title': title, 'text': text,
                    'author': author})
            if len(records) >= LIMIT:
                break
        # insert
        query = 'INSERT INTO vffk (link, title, text, author, updated) ' \
                'VALUES (%s, %s, %s, %s, NOW())'
        records = tuple((r['link'], r['title'], r['text'], r['author'])
                for r in records)
        cursor.executemany(query, records)
        connection.commit()
