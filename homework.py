import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 30
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

logging.basicConfig(
    level=logging.DEBUG,
    filename='telegrambot.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
logger.addHandler(handler)

formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
handler.setFormatter(formatter)

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.info(f'Сообщение {message} отправлено в чат')
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения в чат: {error}')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            message_error = f'Ошибка HTTPStatus: {response.status_code}'
            logger.error(message_error)
            raise Exception(message_error)
        return response.json()
    except Exception as error:
        logger.error(error)
        raise Exception(error)


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    if response is None:
        raise TypeError('Ответ содержит None')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('"homeworks" не является списком')
    if 'homeworks' not in response:
        raise KeyError(
            'В словаре ответа отсутствует ключ "homeworks"'
        )
    if len(response['homeworks']) == 0:
        raise IndexError(
            'Домашних работ нет в запрошенном диапозоне времени'
        )
    return response['homeworks'][0]


def parse_status(homework):
    """
    Извлекает из информации о конкретной домашней работе статус этой работы.
    """
    if homework is None:
        raise Exception('В запросе нет ни одной домашней работы')
    if 'homework_name' not in homework:
        raise KeyError('Не найден "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Не найден "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise Exception('Неизвестный статус работы')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения"""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message_error = 'Проблема с переменными окружения!'
        logger.critical(message_error)
        raise exceptions.EnvironmentVariablesAreMissing(message_error)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    status = None
    error_status = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            message = parse_status(check_response(response))
            if message != status:
                send_message(bot, message)
                status = message
            else:
                logger.info('Обновления статуса нет')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if error_status != str(error):
                error_status = str(error)
                send_message(bot, message)
            logger.error(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
