from datetime import date, timedelta
import sys


from bs4 import BeautifulSoup
from mysql.connector import connect, Error
from requests_cache import CachedSession
from urllib.parse import urldefrag, urljoin


import config


LIMIT = 50 # how many items to scrape in one go, at most
MONTHS = ('januar', 'februar', 'maerz', 'april', 'mai', 'juni', 'juli',
        'august', 'september', 'oktober', 'november', 'dezember')


def date_to_index_url(date):
    year = date.year
    month = MONTHS[date.month - 1]
    return f'https://www.titanic-magazin.de/fachmann/{year}/{month}'


if __name__ == '__main__':
    with connect(host=config.db_host, user=config.db_user,
            password=config.db_pass, database=config.db_name) \
            as connection, connection.cursor() as cursor:
        # see which links we already scraped
        query = 'SELECT link FROM vffk';
        cursor.execute(query)
        links = set(link for (link,) in cursor.fetchall())
        # prepare scraping
        session = CachedSession('vffk', backend='memory')
        index_urls = tuple(
            date_to_index_url(date)
            for date in (
                date.today() - timedelta(months=1),
                date.today(),
                date.today() + timedelta(months=1),
            )
        )
        # scrape
        for index_url in index_urls:
            print(f'scraping {index_url}')
            index_res = session.get(index_url)
            index_soup = BeautifulSoup(index_res.content, 'html.parser')
            records = []
            for a in reversed(index_soup.select('div#briefe > nav > ul > li > a')):
                link = urljoin(index_url, a.get('href'))
                print(link, file=sys.stderr)
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
                if not text:
                    text = author
                    author = ''
                records.append({'link': link, 'title': title, 'text': text,
                        'author': author})
                if len(records) >= LIMIT:
                    break
            query = 'INSERT INTO vffk (link, title, text, author, updated) ' \
                    'VALUES (%s, %s, %s, %s, NOW())'
            records = tuple((r['link'], r['title'], r['text'], r['author'])
                    for r in records)
            cursor.executemany(query, records)
            connection.commit()
