import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s"
)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение: {message}')
    except Exception as error:
        message = f'Сбой в отправке сообщения с ошибкой {error}'
        logger.error(message)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    for env in (TELEGRAM_CHAT_ID, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID):
        if env is None:
            message = (
                f'Отсутствует обязательная переменная окружения {env}.'
                'Программа принудительно остановлена.'
            )
            logger.critical(message)
            exit()


def get_api_answer(timestamp):
    """
    Выполняет запрос к API-сервиса.
    В качестве параметра в функцию передается временная метка.
    В случае успешного запроса должна вернуть ответ API,
    приведя его из формата JSON к типам данных Python,
    иначе отправить сообщение в телеграмм об ошибке.
    """
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        status_code = response.status_code
        if status_code != HTTPStatus.OK:
            message = (
                f'Эндпоинт {ENDPOINT} недоступен. '
                f'Код ответа API: {status_code}.'
                f'Ошибка: {response.text}'
            )
            logger.error(message)
            raise Exception(message)
    except Exception as error:
        raise Exception(error)
    else:
        logger.info('Запрос к API выполнен')
        return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if response is None:
        raise Exception('Ответ не получен')
    if not isinstance(response, dict):
        raise TypeError(f'Ожидается словарь, получен {type(response)}')
    if 'homeworks' not in response or 'current_date' not in response:
        raise KeyError("Отсутствуют ключи 'homeworks,current_date' в ответе")
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            f'Ожидается список, получен {type(response["homeworks"])}'
        )
    return response.get('homeworks')


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой работы.
    В случае успеха, функция возвращает подготовленную для отправки в Telegram
    строку, содержащую один из вердиктов словаря.
    """
    if 'status' not in homework:
        raise KeyError('Нет такого ключа "status"')
    status = homework.get('status')
    if 'homework_name' not in homework:
        raise KeyError('Нет такого ключа "homework_name"')
    homework_name = homework.get('homework_name')
    if status not in HOMEWORK_VERDICTS:
        raise Exception(f'Неожиданный статус - {status}')
    else:
        verdict = HOMEWORK_VERDICTS.get(status)
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    old_status = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                new_status = homeworks[0].get('status')
                if new_status != old_status:
                    send_message(bot, parse_status(homeworks[0]))
                    old_status = new_status
                else:
                    logger.debug('Нет новых статусов')
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
