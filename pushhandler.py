import pushbullet
import logging
from pycoingecko import CoinGeckoAPI
import json
import sqlite3
from time import sleep
from datetime import datetime, timedelta
from threading import Thread
from statistics import mean
import os

logging.basicConfig(filename='doge_alert.log', encoding='utf-8', level=logging.INFO)
strf = "%Y-%m-%d %H:%M:%S"

class PushHandler:
    def __init__(
        self
        ):
        try:
            path = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(path, r"id.json")
            f = open(json_path, "r")
            token = json.load(f)
            token = token["api"]
            self.pb = pushbullet.PushBullet(token)
        except Exception as e:
            logging.error(f"Could not load key: {e}")

    def send_alert(self, message):
        try:
            self.pb.push_note("DogeCoin Alert",str(message))
            logging.info(f"Sent alert {message} at: {datetime.now()}")
        except Exception as e:
            logging.info(f"Error sending message: {e}")
            print(e)

class CoinInfoGetter(Thread):
    def __init__(
        self,
        database):
        Thread.__init__(self)
        self.cg = CoinGeckoAPI()
        self.coin_database = database
        self.last_price_time = None
        self.last_price = None
        self.record = None
        self.running = True
    
    def get_price(self):
        global strf
        current_time = datetime.now()
        try:
            data = self.cg.get_price(ids='dogecoin', vs_currencies='usd')
            price = data["dogecoin"]["usd"]
            current_time = datetime.now().strftime(strf)
            record = current_time , price
            self.last_price = price
            self.last_price_time = current_time
            self.record = record
            if isinstance(record, tuple):
                try:
                    with sqlite3.connect(self.coin_database.database) as con:
                        cur = con.cursor()
                        sql = ("""INSERT INTO dogecoin (date, price) VALUES (?,?)""" )
                        cur.execute(sql, record)
                        con.commit()
                    return 1
                except Exception as e:
                    self.running = False
                    logging.error(f"Could not insert values:{e}")
                    print(e)
            else:
                logging.error(f"Could not parse record, needs to be tuple")
                return 0
            return price
        except Exception as e:
            self.running = False
            logging.info(f"Error getting Price")
            print(e)

    def run(self):
        while True:
            global strf
            sleep(5)
            try:
                self.get_price()
            except Exception as e:
                self.running = False
                logging.error(f"Could not get price: {e}")
                print(e)


class CoinDatabase:
    def __init__(
        self,
        database="dogecoin.db"):
        self.database = database
        try:
            self.con = sqlite3.connect(
                database,detect_types=sqlite3.PARSE_DECLTYPES |
                                                        sqlite3.PARSE_COLNAMES)
            self.cur = self.con.cursor()
        except Exception as e:
            logging.error(f"Could not connect to db: {e}")
            print(e)
        try:
            self.cur.execute("""CREATE TABLE IF NOT EXISTS dogecoin (date timestamp, price)""")
        except Exception as e:
            logging.error(f"Could not create table: {e}")
            print(e)

    def get_last_price(self):
        try:
            self.cur.execute("""SELECT * from dogecoin LIMIT 1""" )
            data = self.cur.fetchone()
            if len(data) != 0:
                return data
        except Exception as e:
            logging.error(f"Failed to get last price: {e}")
            print(e)

    def get_tables(self):
        self.cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = self.cur.fetchall()
        if len(tables) == 0:
            return 0 
        else:
            return tables

    def get_data_range(self, time):
        global strf
        with self.con as con:
            cur = con.cursor()
            sql = ("SELECT * FROM dogecoin WHERE date BETWEEN ? and ?")
            values = time, datetime.now().strftime(strf)
            try:
                cur.execute(sql, values)
                result = cur.fetchall()
                return result
            except Exception as e:
                logging.error(f"Could not get data: {e}")
                print(e)
                return 0

    def insert_record(self, values):
        if isinstance(values, tuple):
            try:
                with self.con as con:
                    cur = con.cursor()
                    sql = ("""INSERT INTO dogecoin (date, price) VALUES (?,?)""" )
                    cur.execute(sql, values)
                    con.commit()
                return 1
            except Exception as e:
                logging.error(f"Could not insert values:{e}")
                print(e)
        else: 
            return 0

class DogeEngine:
    def __init__(
        self,
        push_handler: PushHandler,
        coin_getter: CoinInfoGetter,
        coin_database: CoinDatabase):
        self._push_handler = None
        self._coin_getter = None
        self._coin_database = None
        self.last_price = None

        self._push_handler = push_handler
        self._coin_getter = coin_getter
        self._coin_database = coin_database
        self.last_alert_time = datetime.now()
        self.first_send = True

    def get_db_last_price(self):
        try:
            data = self._coin_database.get_last_price()
            self.last_price = data[1]
            return self.last_price
        except Exception as e:
            logging.error(f"Could get db values:{e}")
            print(e)

    def get_last_5_mins(self):
        global strf
        try:
            current_time = datetime.now()
            past5 = current_time - timedelta(minutes=5)
            past5 = past5.strftime(strf)
            data = self._coin_database.get_data_range(past5)
            if len(data) == 0:
                return
            else:
                first_data = data[0][1]
                last_data = data[len(data) - 1][1]
                all_data = []
                for _ in range(len(data)):
                    all_data.append(data[_][1])
                data_mean = mean(all_data)
        except Exception as e:
            logging.error(f"Couldn't get db values:{e}")
            print(e)
        return first_data, last_data, data_mean

    def get_last_x_mins(self, timespan: int):
        global strf
        try:
            current_time = datetime.now()
            past = current_time - timedelta(minutes=timespan)
            past = past.strftime(strf)
            data = self._coin_database.get_data_range(past)
            if len(data) == 0:
                return
            else:
                first_data = data[0][1]
                last_data = data[len(data) - 1][1]
                all_data = []
                for _ in range(len(data)):
                    all_data.append(data[_][1])
                data_mean = mean(all_data)
        except Exception as e:
            logging.error(f"Couldn't get db values:{e}")
            print(e)
        return first_data, last_data, data_mean

    def data_check(self, threshold: float):
        """
        Threadhold is a float that is a percent 1.0 = 1%
        """
        try:
            first_data, last_data, mean_5_min = self.get_last_5_mins()
            price_change = (mean_5_min - first_data) / first_data * 100
            price_change = round(price_change, 3)
            if abs(price_change) > threshold:
                delta = (datetime.now() - self.last_alert_time)
                if delta.seconds > 450 or self.first_send == True:
                    self.first_send = False
                    if last_data > first_data:
                        self.last_alert_time = datetime.now()
                        self._push_handler.send_alert(f"Doge price increased: {price_change}%\n from: {first_data} to: {last_data}")
                    if last_data < first_data:
                        self._push_handler.send_alert(f"Doge price dropped: {price_change}%\n from: {first_data} to: {last_data}")
                        self.last_alert_time = datetime.now()
        except Exception as e:
            print(e)
            logging.error(f"Could not get data: {e}")
            pass
    def run(self):
        pass

def mainApp():
    dogePushHandler = PushHandler()
    dogeCoinDatabase = CoinDatabase()
    dogeCoinInfoGetter = CoinInfoGetter(dogeCoinDatabase)
    dogeEngine = DogeEngine(dogePushHandler, dogeCoinInfoGetter, dogeCoinDatabase)
    dogeCoinInfoGetter.name = "CoinGeko Thread"
    dogeCoinInfoGetter.start()
    i = 0
    while True:
        print(dogeEngine._coin_getter.record)
        print(f"Iteration: {i}")
        i += 1
        dogeEngine.data_check(0.5)
        sleep(10)

if __name__ == "__main__":
    mainApp()
