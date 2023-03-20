import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from telegram import Bot
from dotenv import load_dotenv


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='homework.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)


def check_tokens():
    """Проверка переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправление сообщения ботом."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(
            f'Сообщение в чат отправлено: {message}'
        )
        return True
    except telegram.TelegramError as telegram_error:
        logger.error(
            f'Сообщение в чат не отправлено: {telegram_error}'
        )


def get_api_answer(timestamp):
    """Запрос к сервису API Яндекс.Практикум."""
    params = {'from_date': timestamp}
    try:
        homework_status = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if homework_status.status_code != HTTPStatus.OK:
            logger.error('Ошбика при запросе к API')
            raise Exception('Ошбика при запросе к API')
        return homework_status.json()
    except Exception as Error:
        logger.error(f'Ошибка {Error} при запросе к API')
        raise Exception(f'Ошибка {Error}')


def check_response(response):
    """Проверка ответа API Яндекс.Практикум на корректность."""
    if type(response) is not dict:
        logger.error('Отсутствует статус в homeworks')
        raise TypeError('Ответ сервера не является словарем')
    if 'homeworks' not in response.keys():
        logger.error('Отсутствует ключ homeworks')
        raise KeyError('Отсутствует ключ homeworks')
    if 'current_date' not in response.keys():
        logger.error('Отсутсвует ключ current_date')
        raise KeyError('Отсутсвует ключ current_date')
    if type(response['homeworks']) is not list:
        logger.error('Данные не являются списком!')
        raise TypeError('Данные не являются списком!')
    return response['homeworks'][0]


def parse_status(homework):
    """Получение статуса домашней работы."""
    if not isinstance(homework, dict):
        logger.error('Данные не являются списком!')
        raise KeyError('Данные не являются списком!')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None:
        raise Exception(f'homework_name отсутствует {homework_name}')
    if homework_status is None:
        raise Exception(f'homework_status отсутствует {homework_status}')
    if homework_status not in HOMEWORK_VERDICTS:
        logger.error('Отсутсвуют ожидаемые ключи')
        raise KeyError('Отсутсвуют ожидаемые ключи')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствие обязательных переменных окружения')
        raise SystemExit('Отсутствие обязательных переменных окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''
    pre_message = None
    while True:
        try:
            response = get_api_answer(timestamp)
            check = check_response(response)
            message = parse_status(check)
            if last_message != message:
                last_message = message
                send_message(bot, last_message)
                time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != pre_message and send_message(
                    bot, message):
                pre_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
