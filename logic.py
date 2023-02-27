import os
import time
from datetime import datetime

import requests as requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pymongo import MongoClient

from ythread import YThread

load_dotenv()


class Yad2Logic:
    OFFSET = 1
    cookie = ""
    apts = []

    def __init__(self, city_code: int):
        self.city_code = city_code

    def get_data(self):
        data = self._prepare_data()
        try:
            self._save_data(data)
            return True
        except Exception:
            return False

    def _prepare_data(self):
        offset = self.OFFSET

        session = requests.Session()

        parsed_html = self._get_apt_page(offset)
        all_offset = (
            int(parsed_html.find_all("button", {"class": "page-num"})[-1].get_text().strip())
        )

        threads = []

        print(f"All offset: {all_offset}")

        for i in range(all_offset):
            t = YThread(
                session,
                offset,
                self._process_apts
            )
            threads.append(t)
            offset += self.OFFSET

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        c_apts = self.apts
        return c_apts

    def _get_apt_page(self, offset: int):
        url = (
            "https://www.yad2.co.il/realestate/rent?"
            "city=" + str(self.city_code) +
            "&page=" + str(offset) +
            "&priceOnly=1"
        )

        print(f"Scraping {url}")

        r = requests.get(
            url,
            headers=self._get_headers()
        )

        html = r.content
        parsed_html = BeautifulSoup(html, "lxml")

        h_captcha = parsed_html.find("div", {"class": "h-captcha"})
        if h_captcha:
            site_key = h_captcha.get("data-sitekey").replace('-', '')
            print("sitekey", site_key)
            api_key = os.getenv("CAPTCHA_API_KEY")

            form = {
                "method": "userrecaptcha",
                "googlekey": site_key,
                "key": api_key,
                "pageurl": url,
                "json": 1
            }

            response = requests.post('https://2captcha.com/in.php', data=form)
            print(response.content)
            request_id = response.json()['request']

            url = f"http://2captcha.com/res.php?key={api_key}&action=get&id={request_id}&json=1"

            status = 0
            while not status:
                res = requests.get(url)
                if res.json()['status'] == 0:
                    time.sleep(3)
                else:
                    requ = res.json()['request']
                    print(requ)

        return parsed_html

    def _get_cookie(self):
        if len(self.cookie):
            return self.cookie

        with requests.Session() as s:
            # generate new cookies by request from the 'refresh' url
            res = s.get('https://gw.yad2.co.il/auth/token/refresh')
            co_dict = res.cookies.get_dict()

            for key in co_dict:
                self.cookie += f'{key}={co_dict[key]}; '

        for c in ('__uzma', '__uzmb', '__uzmc', '__uzmd', '__uzme'):
            # Check if all cookies are created correctly
            if c not in self.cookie:
                raise Exception(
                    "Failed to generate cookies.\n"
                    "Please restart program for new session."
                )

    def _get_headers(self) -> dict:
        headers = {'Accept': 'application/json, text/plain, */*',
                   'Accept-Encoding': 'gzip, deflate, br',
                   'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
                   'Connection': 'keep-alive', 'Host': 'www.yad2.co.il',
                   'mobile-app': 'false',
                   'Referer': 'https://www.yad2.co.il/realestate/forsale',
                   'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
                   'sec-ch-ua-platform': '"Windows"',
                   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
                   'Cookie': self._get_cookie()}

        return headers

    def _get_item_date(self, item: BeautifulSoup) -> str:
        if (
            (today := item.find("span", {"class": "date"}))
            and ((today := today.string.strip()) != "עודכן היום")
        ):
            return today
        else:
            return datetime.today().strftime('%d/%m/%Y')

    def _process_apts(self, offset):
        parsed_html = self._get_apt_page(offset)
        apts = parsed_html.find_all("div", {"class": "feeditem table"})
        for apt in apts:
            try:
                item_id = apt.find_all("div", {"class": "feed_item"})[0]
                item_id = item_id.get('item-id')

                try_title = apt.find("span", {"class": "title"})
                if try_title:
                    title = try_title
                else:
                    title = apt.find("div", {"class": "title"})
                title = title.text.strip()

                try_subtitle = apt.find("span", {"class": "subtitle"})
                if try_subtitle:
                    subtitle = try_subtitle
                else:
                    subtitle = apt.find("div", {"class": "sub_title"})
                subtitle = subtitle.text
                subtitle = tuple(
                    sub_part.strip() for sub_part in subtitle.split(',')
                )

                type_ = subtitle[0]
                city = subtitle[-1]

                try_attr = tuple(
                    span.string for span in apt.find(
                        "div", {"class": "middle_col"}
                    ).find_all('span')
                )

                if len(try_attr) != 0:
                    attr = try_attr
                    rooms, floor, size = str(attr[0]), str(attr[2]), str(
                        attr[4])
                else:
                    attr = tuple(
                        span.string for span in apt.find(
                            "div", {"class": "middle_col"}
                        ).find_all('dt')
                    )
                    rooms, floor, size = str(attr[0]), str(attr[1]), str(attr[2])
                floor = 0 if floor.strip() == 'קרקע' else floor
                rooms = -1 if rooms == "-" else float(rooms)
                size = -1 if size == "לא צוין" else int(size)

                try_price = apt.find("div", {"class": "price"})
                if try_price:
                    price = try_price
                else:
                    price = apt.find("div", {"class": "left_col"})
                price = price.string.strip()
                price = int(price[:-2].replace(',', ''))

                url = f"https://yad2.co.il/item/{item_id}"

                apt_data = {
                    "price": price,
                    "address": title,
                    "city": city,
                    "type": type_,
                    "rooms": rooms,
                    "floor": int(floor),
                    "size": size,
                    "update": self._get_item_date(apt),
                    "scrape_date": datetime.today().strftime('%d/%m/%Y'),
                    "item_id": item_id,
                    "url": url
                }

                self.apts.append(apt_data)
            except AttributeError as e:
                print(apt)
                raise e

    def _save_data(self, data):
        d_yad2 = self._get_database()
        c_rentals = d_yad2["rentals"]
        c_updates = d_yad2["updates"]
        for apt in data:
            found_apt = c_rentals.find_one({"item_id": apt["item_id"]})
            if not found_apt:
                c_rentals.insert_one(apt)
            else:
                if found_apt.get("price") != apt["price"]:
                    c_updates.insert_one({
                        "apt_id": found_apt.get("_id"),
                        "prev_price": found_apt.get("price"),
                        "curr_price": apt["price"],
                        "update": apt["update"],
                        "scrape_date": apt["scrape_date"]
                    })
                    c_rentals.find_one_and_update(
                        {"_id": found_apt.get("_id")},
                        {
                            '$set': {"price": apt["price"]}
                        }
                    )

    @staticmethod
    def _get_database():
        db_conn = os.getenv('MONGO_CONNECTION_STRING')
        client = MongoClient(db_conn)
        return client["Yad2Scraper"]
