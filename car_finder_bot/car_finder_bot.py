#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
from threading import Thread
import os

import pickle
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, ConversationHandler, CallbackQueryHandler, MessageHandler, Filters
from telegram.utils import request

from car_finder_bot.util import send_message, R, is_subscribed, Options, build_menu, get_callback_data, REQUEST_KWARGS, get_brand_display, \
    get_model_display, \
    get_filter_display

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


def wait_for_sales(chat_id, bot):
    logger.info(f'New subscriber waiting for updates: {chat_id}')
    while True:
        try:
            new_sale = R.brpop(chat_id)
            message = new_sale[1].decode('utf-8')
            logger.info(f'Got new message {message}')
            sent = send_message(bot, chat_id, message)
            if not sent:
                R.lpush(chat_id, new_sale)
        except Exception as e:
            logger.error(f'Error occurred: {e}. Chat id: {chat_id}')


def start(update, context):
    chat_id = update.message.chat_id
    if not is_subscribed(chat_id):
        R.hset('telegram_chat_ids', chat_id, pickle.dumps(context.bot.__reduce__()))
        t = Thread(target=wait_for_sales, args=(chat_id, context.bot))
        t.start()
        update.message.reply_text('Ждите уведомления о новых объявлениях на продажу')
    else:
        update.message.reply_text('Вы уже подписаны на обновления!')


def stop(update, context):
    chat_id = update.message.chat_id
    if is_subscribed(chat_id):
        R.hdel('telegram_chat_ids', chat_id)
        update.message.reply_text('Вы успешно отписались от обновлений')
    else:
        update.message.reply_text('Вы уже отписались ;)')


def filter_sales(update, context):
    if 'filter' not in context.user_data:
        context.user_data['filter'] = {
            'raw': {},
            'display': {},
        }
    button_list = [
        InlineKeyboardButton(text="По марке/модели автомобиля", callback_data=f'{Options.BRAND.value}'),
        # InlineKeyboardButton(text="По радиусу поиска объявления", callback_data=f'{Options.DISTANCE.value}'),
        # InlineKeyboardButton(text="По цене автомобиля", callback_data=f'{Options.PRICE.value}'),
        InlineKeyboardButton(text="Отмена", callback_data=f'{Options.CANCEL.value}'),
    ]
    if update.message:
        reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1), one_time_keyboard=True)
        update.message.reply_text(text="Выберите фильтр", reply_markup=reply_markup)
    else:
        button_list.append(InlineKeyboardButton(text="Готово", callback_data=f'{Options.FINISH_FILTER.value}'))
        reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1), one_time_keyboard=True)
        filter_text = get_filter_display(context.user_data['filter']['display'])
        update.callback_query.edit_message_text(text=f"Текущий фильтр:\n{filter_text}\n\nПродолжите настройку фильтра, либо закончите нажав Финиш")
        update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)

    return Options.PROCESS_FILTER_SELECT.value


def process_filter_select(update, context):
    callback_data = get_callback_data(update)
    if callback_data:
        filter_name = Options(callback_data).name.lower()
        logger.info(f'process filter select {filter_name}')
        if callback_data == Options.BRAND.value:
            process_brand_filter(update, context)
            return Options.MODEL.value
        if callback_data == Options.DISTANCE.value:
            process_distance_filter(update, context)
            return Options.CITY_SELECTED.value
        if callback_data == Options.PRICE.value:
            process_price_filter(update, context)
            return Options.SELECT_FILTER.value
        if callback_data == Options.CANCEL.value:
            process_cancel_filter(update, context)
            return ConversationHandler.END
        if callback_data == Options.FINISH_FILTER.value:
            process_finish_filter(update, context)
            return ConversationHandler.END


def process_distance_filter(update, context):
    cities = R.hgetall('1:cities').items()
    cities = sorted(cities, key=lambda item: item[1])
    button_list = [
        KeyboardButton(text=name.decode('utf-8')) for _, name in cities
    ]
    reply_markup = ReplyKeyboardMarkup(build_menu(button_list, n_cols=1), one_time_keyboard=True)
    context.bot.send_message(update.effective_chat.id, 'Выберите ваш город', reply_markup=reply_markup)


def process_city_selected(update, context):
    city_name = update.message.text
    if city_name:
        context.user_data['filter']['raw']['city__name'] = city_name
        context.user_data['filter']['display']['Город'] = city_name
        update.message.reply_text('Задайте радиус в километрах, в котором необходимо искать объявления')
        return Options.RADIUS_SET.value


def process_radius_set(update, context):
    radius = update.message.text
    if radius:
        context.user_data['filter']['raw']['radius'] = radius
        context.user_data['filter']['display']['Город'] = f"context.user_data['filter']['display']['Город'] + {radius}"
        return Options.SELECT_FILTER.value


def process_cancel_filter(update, context):
    if 'filter' in context.user_data:
        context.user_data.pop('filter')
    # reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton('OK', callback_data='ok')]], one_time_keyboard=True)
    update.callback_query.edit_message_text(text="Создание фильтра отменено")
    # update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


def process_price_filter(update, context):
    pass


def process_finish_filter(update, context):
    logger.info('Filter created!')


def process_brand_filter(update, context):
    brands = R.hgetall('brands').items()
    brands = sorted(brands, key=lambda item: item[1])
    button_list = [
        InlineKeyboardButton(text=brand.decode('utf-8'), callback_data=f'{brand_id.decode("utf-8")}:models') for brand_id, brand in brands
    ]
    button_list.append(InlineKeyboardButton(text="Отмена", callback_data=f'{Options.CANCEL.value}'))
    reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1), one_time_keyboard=True)
    update.callback_query.edit_message_text(text="Выберите брэнд")
    update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


def filter_by_model(update, context):
    logger.info('by model')
    callback_data = get_callback_data(update, t=str)
    if callback_data:
        context.user_data['filter']['raw']['brand_id'] = callback_data.split(':')[0]
        context.user_data['filter']['display']['Марка'] = get_brand_display(callback_data)
        models = R.hgetall(callback_data).items()
        models = sorted(models, key=lambda item: item[1])
        button_list = [
            InlineKeyboardButton(text=model.decode('utf-8'), callback_data=f'{model_id.decode("utf-8")}') for model_id, model in models
        ]
        button_list.append(InlineKeyboardButton(text='Любая', callback_data=str(Options.ANY_MODEL.value)))
        button_list.append(InlineKeyboardButton(text="Отмена", callback_data=f'{Options.CANCEL.value}'))
        reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1), one_time_keyboard=True)
        update.callback_query.edit_message_text(text=f"Выберите модель {get_brand_display(callback_data)}")
        update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)
        return Options.MODEL_SELECTED.value


def model_selected(update, context):
    model_id = get_callback_data(update)
    if model_id and model_id != Options.ANY_MODEL.value:
        context.user_data['filter']['raw']['model_id'] = model_id
        model_display = get_model_display(context.user_data['filter']['raw']['brand_id'], model_id)
    else:
        model_display = 'Любая'
    context.user_data['filter']['display']['Модель'] = model_display
    button_list = [
        InlineKeyboardButton(text='Далее', callback_data='next'),
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1), one_time_keyboard=True)
    update.callback_query.edit_message_text(text=f"Вы выбрали модель: {model_display}")
    update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)
    return Options.SELECT_FILTER.value


def filter_by_price(update, context):
    logger.info('by price')


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    updater = Updater(os.environ.get('TOKEN', None), request_kwargs=REQUEST_KWARGS, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_error_handler(error)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('filter', filter_sales)],
        states={
            Options.SELECT_FILTER: [CallbackQueryHandler(filter_sales)],
            Options.MODEL.value: [CallbackQueryHandler(filter_by_model)],
            Options.MODEL_SELECTED.value: [CallbackQueryHandler(model_selected)],
            Options.CITY_SELECTED.value: [MessageHandler(Filters.text, process_city_selected)],
            Options.PRICE.value: [CallbackQueryHandler(filter_by_price)],
            Options.PROCESS_FILTER_SELECT.value: [CallbackQueryHandler(process_filter_select)],
            Options.RADIUS_SET.value: [MessageHandler(Filters.text, process_radius_set)],
        },
        fallbacks=[CallbackQueryHandler(filter_sales)],
    )

    dp.add_handler(conv_handler)
    # Start the Bot
    updater.start_polling(allowed_updates=[])
    try:
        for chat_id, pickled_bot in R.hgetall('telegram_chat_ids').items():
            bot_class, (token, base_url, file_base_url) = pickle.loads(pickled_bot)
            proxy_request = request.Request(**REQUEST_KWARGS)
            bot = bot_class(token, base_url, file_base_url, proxy_request)
            t = Thread(target=wait_for_sales, args=(chat_id.decode('utf-8'), bot))
            t.start()
    except AttributeError:
        pass

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()
