# -*- coding: utf-8 -*-
# Owner: Bulat <bulat.kurbangaliev@cinarra.com>
import enum
import logging
import os
from time import sleep

import redis
from telegram.vendor.ptb_urllib3.urllib3.exceptions import ProtocolError, HTTPError as tele_HTTPError

__author__ = 'ilov3'
logger = logging.getLogger(__name__)

R = redis.Redis(os.getenv('REDIS_HOST', 'localhost'))


class Options(enum.Enum):
    SELECT_FILTER = 0
    PROCESS_FILTER_SELECT = 1
    BRAND = 2
    MODEL = 3
    DISTANCE = 4
    CITY_SELECTED = 5
    PRICE = 6
    ANY_MODEL = 7
    ANY_CITY = 8
    FINISH_FILTER = 9
    MODEL_SELECTED = 10
    RADIUS_SET = 11
    CANCEL = 12


def is_subscribed(chat_id):
    return R.hexists('telegram_chat_ids', chat_id)


def build_menu(buttons,
               n_cols,
               header_buttons=None,
               footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return menu


def get_callback_data(update, t=int):
    try:
        return t(update.callback_query.data)
    except (AttributeError, TypeError):
        pass


def send_message(bot, chat_id, message, retries=5):
    while retries:
        try:
            bot.send_message(chat_id, message)
            return True
        except (ProtocolError, tele_HTTPError) as e:
            logger.error(f'Error while sending message: {e}. Retries: {retries}')
            sleep(int(10 / retries))
            retries -= 1


def get_brand_display(brand_key):
    key, _ = brand_key.split(':')
    return R.hget('brands', key).decode('utf-8')


def get_model_display(brand_key, model_key):
    return R.hget(f'{brand_key}:models', model_key).decode('utf-8')


def get_filter_display(filters):
    return '\n'.join([f'{f}: {value}' for f, value in filters.items()])


def get_token():
    return os.environ.get('TOKEN')
