import json
import re
import sys

import dateparser
from fake_useragent import UserAgent
from requests_html import HTMLSession

from urllib.parse import unquote
import requests
from bs4 import BeautifulSoup

from .app import app

session = HTMLSession()
ua = UserAgent()


def _clean(text):
    text = text.replace('\xa0', ' ').replace(',-', '').replace(' m²', '')
    try:
        text = int(re.sub(r'kr$', '', text).replace(' ', ''))
    except ValueError:
        pass

    return text


def _parse_data_lists(html):
    data = {}
    skip_keys = ['Mobil', 'Fax']  # Unhandled data list labels

    data_lists = html.find('dl')
    for el in data_lists:
        values_list = iter(el.find('dt, dd'))
        for a in values_list:
            _key = a.text
            a = next(values_list)
            if _key in skip_keys:
                continue
            data[_key] = _clean(a.text)

    return data


def _scrape_viewings(html):
    viewings = set()
    els = html.find('time')
    for el in els:
        # Ninja parse dt range string in norwegian locale. Example: "søndag 08. april, kl. 13:00–14:00"
        split_space = el.text.strip().split(' ')
        if len(split_space) < 5:
            continue
        date, time_range = ' '.join(split_space[1:]).replace(' kl. ', '').split(',')
        # start_hour, start_min = time_range.split('–')[0].split(':')
        dt = dateparser.parse(date, languages=['nb'])
        if dt:
            # dt = dt.replace(hour=int(start_hour), minute=int(start_min))
            viewings.add(dt.date().isoformat())
    return list(viewings)


def _calc_price(ad_data):
    debt = ad_data.get('Fellesgjeld', 0)
    cost = ad_data.get('Omkostninger', 0)
    return ad_data['Totalpris'] - debt - cost

def _extract_lat_lng(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text)

    metas = soup.find_all('meta')
    meta_content = [ meta.attrs['content'] for meta in metas if 'name' in meta.attrs and meta.attrs['name'] == 'FINN.pulseOptions' ]
    content_location = eval(unquote(meta_content[0]))['contentLocation']

    lat = content_location['latitude']
    lng = content_location['longitude']

    return lat, lng

def scrape_ad(finnkode):
    url = 'https://www.finn.no/realestate/homes/ad.html?finnkode={code}'.format(code=finnkode)
    r = session.get(url, headers={'user-agent': ua.random})
    r.raise_for_status()

    html = r.html

    postal_address_element = html.find('h1 + p', first=True)
    if not postal_address_element:
        return

    ad_data = {
        'Postadresse': postal_address_element.text,
        'url': url,
    }

    viewings = _scrape_viewings(html)
    if viewings:
        ad_data['Visningsdatoer'] = viewings
        ad_data.update({'Visningsdato {}'.format(i): v for i, v in enumerate(viewings, start=1)})

    ad_data.update(_parse_data_lists(html))

    ad_data['Prisantydning'] = _calc_price(ad_data)

    ad_data['latitude'], ad_data['longitude'] = _extract_lat_lng(url)

    return ad_data


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Invalid number of arguments.\n\nUsage:\n$ python finn.py FINNKODE')
        exit(1)

    ad_url = sys.argv[1]
    ad = scrape_ad(ad_url)
    print(json.dumps(ad, indent=2, ensure_ascii=False))
