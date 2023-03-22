import logging
import os
import time
from http import HTTPStatus
import sys

import requests
import telegram
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

TOKEN_NAMES = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]


def check_tokens():
    """Проверка переменных окружения."""
    for token in TOKEN_NAMES:
        if token is None:
            logging.critical(
                'Отсутсвует обязательная переменная окружения'
            )
            return False
    return True


def send_message(bot, message):
    """Отправление сообщения ботом."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(
            f'Сообщение в чат отправлено: {message}'
        )
        return True
    except Exception as error:
        logging.error(
            f'Сообщение в чат не отправлено: {error}'
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
    except Exception as Error:
        raise Exception(f'Ошибка {Error}')

    if homework_status.status_code != HTTPStatus.OK:
        logging.error('Ошбика при запросе к API')
        raise Exception('Ошбика при запросе к API')
    return homework_status.json()


def check_response(response):
    """Проверка ответа API Яндекс.Практикум на корректность."""
    homeworks = response['homeworks']
    if not isinstance(response, dict):
        logging.error('Отсутствует статус в homeworks')
        raise TypeError(
            'Ответ сервера не является словарем'
            f'должны получить dict, а получили {type(response)}'
        )
    if 'current_date' not in response.keys():
        logging.error('Отсутсвует ключ current_date')
        raise KeyError('Отсутсвует ключ current_date')
    if not isinstance(homeworks, list):
        logging.error('Данные не являются списком!')
        raise TypeError(
            'Данные не являются списком!'
            f'должны получить list, а получили {type(homeworks)}'
        )
    return homeworks[0]


def parse_status(homework):
    """Получение статуса домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутсвует ключ homework_name')
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise KeyError('Отсутсвует ключ status')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        logging.error('Отсутсвуют ожидаемые ключи')
        raise KeyError('Отсутсвуют ожидаемые ключи')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise SystemExit('Отсутствие обязательных переменных окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    last_message = ''
    pre_message = None
    while True:
        try:
            response = get_api_answer(timestamp)
            if response is None:
                logging.error('Не удалось получить ответа от API')
                send_message(bot, 'Не удалось получить ответа от API')
            check = check_response(response)
            message = parse_status(check)
            if last_message != message:
                last_message = message
                send_message(bot, last_message)
                timestamp = int(time.time())
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != pre_message and send_message(
                    bot, message):
                pre_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    file_handler = logging.FileHandler(filename='homework.log')
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[file_handler, stdout_handler],
        format='%(asctime)s, %(levelname)s, %(message)s '
               '%(funcName)s, %(lineno)d',
    )
    main()
