"""
Нагрузка плагина SPP

1/2 документ плагина
"""
import datetime
import logging
import os
import re
import time

import dateutil.parser
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.common import NoSuchElementException

from src.spp.types import SPP_document


class JCB:
    """
    Класс парсера плагина SPP

    :warning Все необходимое для работы парсера должно находится внутри этого класса

    :_content_document: Это список объектов документа. При старте класса этот список должен обнулиться,
                        а затем по мере обработки источника - заполняться.


    """

    REF_NAME = 'jcb'
    HOST = 'https://www.global.jcb/en/press/index.html'

    YEAR_BEGIN = 2023
    HOME_URL = 'https://www.global.jcb/en/press/index.html'
    TEMPLATE_URL = 'https://www.global.jcb/en/press/index.html?year={year}'
    _content_document: list[SPP_document]

    def __init__(self, webdriver: WebDriver, *args, **kwargs):
        """
        Конструктор класса парсера

        По умолчанию внего ничего не передается, но если требуется (например: driver селениума), то нужно будет
        заполнить конфигурацию
        """
        # Обнуление списка
        self._content_document = []
        self.driver = webdriver

        # Логер должен подключаться так. Вся настройка лежит на платформе
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug(f"Parser class init completed")
        self.logger.info(f"Set source: {self.REF_NAME}")
        ...

    def content(self) -> list[SPP_document]:
        """
        Главный метод парсера. Его будет вызывать платформа. Он вызывает метод _parse и возвращает список документов
        :return:
        :rtype:
        """
        self.logger.debug("Parse process start")
        self._parse()
        self.logger.debug("Parse process finished")
        return self._content_document

    def _parse(self):
        """
        Метод, занимающийся парсингом. Он добавляет в _content_document документы, которые получилось обработать
        :return:
        :rtype:
        """
        # HOST - это главная ссылка на источник, по которому будет "бегать" парсер
        self.logger.debug(F"Parser enter to {self.HOST}")

        # ========================================
        # Тут должен находится блок кода, отвечающий за парсинг конкретного источника
        # -

        self.driver.set_page_load_timeout(40)

        # Получения списка страниц по годам
        current_years: list[int] = self._years_for_parsing()
        news_hrefs: list[str] = []

        for year in current_years:
            self.driver.get(self.TEMPLATE_URL.format(year=str(year)))
            time.sleep(3)
            self._agree_cookie_pass()
            news_list = self.driver.find_elements(By.XPATH,
                                                  '//*[@id="press"]/div[1]/div[1]/div/ul/li')  # список новостей за год

            for news in news_list:
                news_href = news.find_element(By.CLASS_NAME, 'news_href').get_attribute(
                    'href')  # ссылка на страницу новости
                news_hrefs.append(news_href)

        for url in news_hrefs:
            try:
                document = self._parse_news_page(url)  # парсинг страницы новости
                self._content_document.append(document)
                self.logger.info(self._find_document_text_for_logger(document))
            except Exception as e:
                # При ошибке парсинга новости, парсер продолжает свою работу
                self.logger.debug(f'news by link:{news_href} done parse with error')

        # Логирование найденного документа
        # self.logger.info(self._find_document_text_for_logger(document))

        # ---
        # ========================================
        ...

    def _years_for_parsing(self) -> list[int]:
        """
        Метод собирает все доступные года публикаций на сайте и сохраняет только те, которые больше начального года (self.YEAR_BEGIN)
        """
        # Получения списка страниц по года
        current_years: list[int] = []

        self.driver.get(self.HOME_URL)
        time.sleep(3)
        self._agree_cookie_pass()
        _year_list_elements = self.driver.find_elements(By.XPATH,
                                                        '//*[@id="news-category"]/div[1]/ul/li')  # бар с выбором года публикации
        for _year_el in _year_list_elements:
            innerText = _year_el.find_element(By.TAG_NAME, 'a').get_attribute(
                'innerText')  # выбор елемента с годом публикации
            if len(innerText) == 4 and re.match(r"^\d{4}$", innerText) and int(innerText) >= self.YEAR_BEGIN:
                current_years.append(int(innerText))  # Содержится год. Добавляем в список

        return current_years

    def _agree_cookie_pass(self):
        """
        Метод прожимает кнопку agree на модальном окне
        """
        cookie_agree_xpath = '//*[@id="gdpr_i_agree_button"]'

        try:
            cookie_button = self.driver.find_element(By.XPATH, cookie_agree_xpath)
            if WebDriverWait(self.driver, 5).until(ec.element_to_be_clickable(cookie_button)):
                cookie_button.click()
                self.logger.debug(F"Parser pass cookie modal on page: {self.driver.current_url}")
        except NoSuchElementException as e:
            self.logger.debug(f'modal agree not found on page: {self.driver.current_url}')

    def _parse_news_page(self, url: str) -> SPP_document:
        self.driver.get(url)
        time.sleep(1)
        self._agree_cookie_pass()

        _document: SPP_document = SPP_document(None, None, None, None, None, None, {}, None, None)

        try:  # Парсинг даты публикации. Обязательная информация
            # _pub_date_text: str = self.driver.find_element(By.XPATH,'//*[@id="press"]/div[1]/div/div/div[2]/div/div/p/span[contains(class, "news-list--date")]').get_attribute('innerText')
            _pub_date_text: str = WebDriverWait(self.driver, 10).until(ec.presence_of_element_located((By.CLASS_NAME, 'news-list--date'))).get_attribute("innerText")
            _pub_date: datetime.datetime = dateutil.parser.parse(_pub_date_text)
            _document.pub_date = _pub_date
        except Exception as e:
            self.logger.error(f'Page {self.driver.current_url} do not contain a publication date of news. Throw error: {e}')
            raise e

        try:  # Категория новости
            # _category_text: str = self.driver.find_element(By.XPATH,
            #                                                '//*[@id="press"]/div[1]/div/div/div[2]/div/div/p/span[contains(class, "news-list--category")]').get_attribute(
            #     'innerText')
            _category_text: str = WebDriverWait(self.driver, 10).until(
                ec.presence_of_element_located((By.CLASS_NAME, 'news-list--category'))).get_attribute("innerText")
            _document.other_data['category'] = _category_text
        except Exception as e:
            self.logger.error(f'Page {self.driver.current_url} do not contain a category of news. Throw error: {e}')

        try:  # Заголовок новости
            # _title = self.driver.find_element(By.XPATH,
            #                                   '//*[@id="press"]/div[1]/div/div/div[2]/div/div/h1[contains(class, "news_title")]').get_attribute(
            #     'innterText')
            _title: str = WebDriverWait(self.driver, 10).until(
                ec.presence_of_element_located((By.CLASS_NAME, 'news_title'))).get_attribute("innerText")
            _document.title = _title
        except Exception as e:
            self.logger.error(f'Page {self.driver.current_url} do not contain a title of news. Throw error: {e}')
            raise e

        try:  # Аннотация новости
            # _abstract: str = self.driver.find_element(By.XPATH, '//*[@id="press"]/div[1]/div/div/div[2]/div/div/div/p[contains(class, "txtAC")]').get_attribute('innerText')
            _abstract: str = WebDriverWait(self.driver, 10).until(
                ec.presence_of_element_located((By.CLASS_NAME, 'txtAC'))).get_attribute("innerText")
            _document.abstract = _abstract
        except Exception as e:
            self.logger.error(f'Page {self.driver.current_url} do not contain a abstract of news. Throw error: {e}')

        try:  # Text новости
            _text = WebDriverWait(self.driver, 10).until(ec.presence_of_element_located((By.XPATH, '//*[@id="press"]/div[1]/div/div/div[2]/div/div/div'))).get_attribute("innerText")
            _document.text = _text
        except Exception as e:
            self.logger.error(f'Page {self.driver.current_url}. Error parse main text of news. Throw error: {e}')
            raise e

        return _document

    @staticmethod
    def _find_document_text_for_logger(doc: SPP_document):
        """
        Единый для всех парсеров метод, который подготовит на основе SPP_document строку для логера
        :param doc: Документ, полученный парсером во время своей работы
        :type doc:
        :return: Строка для логера на основе документа
        :rtype:
        """
        return f"Find document | name: {doc.title} | link to web: {doc.web_link} | publication date: {doc.pub_date}"

    @staticmethod
    def some_necessary_method():
        """
        Если для парсинга нужен какой-то метод, то его нужно писать в классе.

        Например: конвертация дат и времени, конвертация версий документов и т. д.
        :return:
        :rtype:
        """
        ...

    @staticmethod
    def nasty_download(driver, path: str, url: str) -> str:
        """
        Метод для "противных" источников. Для разных источника он может отличаться.
        Но основной его задачей является:
            доведение driver селениума до файла непосредственно.

            Например: пройти куки, ввод форм и т. п.

        Метод скачивает документ по пути, указанному в driver, и возвращает имя файла, который был сохранен
        :param driver: WebInstallDriver, должен быть с настроенным местом скачивания
        :_type driver: WebInstallDriver
        :param url:
        :_type url:
        :return:
        :rtype:
        """

        with driver:
            driver.set_page_load_timeout(40)
            driver.get(url=url)
            time.sleep(1)

            # ========================================
            # Тут должен находится блок кода, отвечающий за конкретный источник
            # -
            # ---
            # ========================================

            # Ожидание полной загрузки файла
            while not os.path.exists(path + '/' + url.split('/')[-1]):
                time.sleep(1)

            if os.path.isfile(path + '/' + url.split('/')[-1]):
                # filename
                return url.split('/')[-1]
            else:
                return ""
