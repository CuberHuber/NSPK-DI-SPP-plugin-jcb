from selenium import webdriver
from logging import config
from jcb import JCB

config.fileConfig('dev.logger.conf')
driver = webdriver.Chrome()

parser = JCB(driver)
docs = parser.content()

print(*docs, sep='\n\r\n')