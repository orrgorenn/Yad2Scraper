import html
import os
import sys
import time
from datetime import datetime
from random import randint

import requests as requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pymongo import MongoClient
from requests.adapters import HTTPAdapter
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from telegram.constants import ParseMode
from urllib3 import Retry

load_dotenv()


class Yad2Logic:
    OFFSET = 1
    cookie = ""
    apts = []

    def __init__(self, city_code: int):
        self.city_code = city_code
        self.driver = None
        self.telegram_url = "https://api.telegram.org/bot{}/sendMessage"

    def _send_message(self, message: str):
        api_url = self.telegram_url.format(os.getenv('TELEGRAM_TOKEN'))

        try:
            requests.post(
                api_url,
                json={
                    'chat_id': os.getenv('TELEGRAM_CHAT_ID'),
                    'text': message,
                    'parse_mode': ParseMode.HTML
                }
            )
            time.sleep(randint(10, 30))
        except Exception as e:
            print(e)

    def get_data(self):
        data = self._prepare_data()
        try:
            self._save_data(data)
            return True
        except Exception as e:
            raise e
            return False

    def _prepare_data(self):
        offset = self.OFFSET

        session = requests.Session()
        retry = Retry(connect=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        parsed_html = self._get_apt_page(offset)
        all_offset = (
            int(parsed_html.find_all("button", {"class": "page-num"})[-1].get_text().strip())
        )

        print(f"All offset: {all_offset}")

        for i in range(all_offset):
            self._process_apts(offset)
            offset += self.OFFSET

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

        r = None

        try:
            r = requests.get(
                url,
                headers=self._get_headers()
            )
        except Exception:
            pass

        if r:
            html = r.content
            parsed_html = BeautifulSoup(html, "lxml")

            h_captcha = parsed_html.find("div", {"class": "h-captcha"})
            if h_captcha:
                return self._solve_captcha(url)

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
        if parsed_html:
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

                    neighborhood = ""
                    if subtitle[1]:
                        neighborhood = subtitle[1]

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
                        "neighborhood": neighborhood,
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


    def _solve_captcha(self, url):
        options = Options()
        options.headless = True
        options.add_argument("--no-sandbox")
        options.add_argument("--headless")
        options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=options)

        self.driver.get(url)

        html = self.driver.page_source
        parsed_html = BeautifulSoup(html, "lxml")

        h_captcha = parsed_html.find("div", {"class": "h-captcha"})

        site_key = h_captcha.get("data-sitekey")
        api_key = os.getenv("CAPTCHA_API_KEY")

        form = {
            "method": "hcaptcha",
            "sitekey": site_key,
            "key": api_key,
            "pageurl": url,
            "json": 1
        }

        response = requests.post('https://2captcha.com/in.php', data=form)
        request_id = response.json()['request']

        get_url = f"https://2captcha.com/res.php?key={api_key}" \
                  f"&action=get&id={request_id}&json=1"

        print("Waiting for captcha...")
        status = 0
        while not status:
            res = requests.get(get_url)
            if res.json()['status'] == 0:
                time.sleep(5)
                print("Still waiting...")
            else:
                requ = res.json()['request']
                js = f'document.getElementsByName("h-captcha-response")[0].innerHTML="{requ}";'
                self.driver.execute_script(js)
                js = f'document.getElementsByName("g-recaptcha-response")[0].innerHTML="{requ}";'
                self.driver.execute_script(js)
                self.driver.find_element(By.CLASS_NAME, "btn").submit()
                status = 1
                self.driver.quit()
                sys.exit(0)

        time.sleep(5)

        try:
            r = requests.get(
                url,
                headers=self._get_headers()
            )
        except Exception as e:
            print(f"Cant scrape {url}")
            raise e

        html = r.content
        parsed_html = BeautifulSoup(html, "lxml")

        return parsed_html

    def _send_update(self, found_apt, new_apt=True, apt=None):
        message = ""

        if new_apt:
            message += "<b>חדש להשכרה</b>\r\n"
            message += "ב{}, {} - {}\r\n\r\n".format(
                found_apt["city"],
                found_apt["neighborhood"],
                found_apt["address"]
            )
            message += "<b>מחיר:</b> {} ₪\r\n".format(found_apt["price"])
        else:
            message += "<b>עדכון מחיר - {}</b>\r\n".format(found_apt["type"])
            message += "ב{}, {} - {}\r\n\r\n".format(
                found_apt["city"],
                found_apt["neighborhood"],
                found_apt["address"]
            )
            message += "<b>מחיר:</b> <s>{} ₪</s> <b>{} ₪</b>\r\n".format(apt["price"], found_apt["price"])

        message += "<b>קומה:</b> {}\r\n".format(found_apt["floor"])
        message += "<b>חדרים:</b> {}\r\n\r\n".format(found_apt["rooms"])
        message += "<a href='{}'>קישור למודעה</a>".format(found_apt["url"])

        self._send_message(message)

    def _save_data(self, data):
        d_yad2 = self._get_database()
        c_rentals = d_yad2["rentals"]
        c_updates = d_yad2["updates"]
        for apt in data:
            found_apt = c_rentals.find_one({"item_id": apt["item_id"]})
            if not found_apt:
                c_rentals.insert_one(apt)
                self._send_update(apt)
            else:
                if found_apt.get("price") != apt["price"]:
                    self._send_update(apt, False, found_apt)
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
