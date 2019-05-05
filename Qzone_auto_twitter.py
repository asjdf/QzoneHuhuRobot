import requests
import json
import re
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
import selenium.webdriver.support.expected_conditions as EC
import selenium.webdriver.support.ui as ui
windCity = "莆田"
qq = '1656858096'
qq_pwd = ''
def getWindSpeed(city):  # 获取风速
    apiUrl = "https://www.tianqiapi.com/api/?version=v1&city=%s" % city
    try:
        data = requests.get(apiUrl)
        print("获取天气数据成功")
    except:
        print("获取天气数据成功")
    try:
        decode = json.loads(data.text)
        print("解析风力成功")
        print("风力：" + decode['data'][0]['win_speed'])
        return decode['data'][0]['win_speed']
    except:
        print("解析风力数据失败")

# 一直等待某元素可见，默认超时20秒
def is_visible(driver, element, timeout=20):
    try:
        ui.WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((By.ID, element)))
        print("True")
        return True
    except TimeoutException:
        print("False")
        return False
# 一直等待某个元素消失，默认超时20秒
def is_not_visible(driver, element, timeout=20):
    try:
        ui.WebDriverWait(driver, timeout).until_not(EC.visibility_of_element_located((By.ID, element)))
        return True
    except TimeoutException:
        return False
def Qzone(info):
    print("starting")
    browser = webdriver.Firefox()
    print("browser binded to Firefox")
    browser.get('https://qzone.qq.com')
    print("browser.get started")
    browser.switch_to.frame('login_frame')
    print("switched to login frame")
    browser.find_element_by_id('switcher_plogin').click()
    print("clicked Switch button")
    browser.find_element_by_id('u').clear()
    print("User field clear")
    browser.find_element_by_id('u').send_keys(qq)
    print("User field set")
    browser.find_element_by_id('p').clear()
    print("Passwd clear")
    browser.find_element_by_id('p').send_keys(qq_pwd)
    print("Passwd set")
    browser.find_element_by_id('login_button').click()
    print("Login button clicked")
    time.sleep(5)
    browser.switch_to.default_content()
    is_visible(browser, "aIcenter")
    browser.find_element_by_id('aIcenter').click()
    print("we are in " + browser.title)
    print("wait to complete loading page")
    if (is_visible(browser, "$1_substitutor_content") and browser.find_element_by_id('$1_content_content').get_attribute('innerHTML') == ""):
        print("trying to click substitutor")
        browser.find_element_by_id('$1_substitutor_content').click()
        print("clicked. Now substitutor_content not displayed and content_content displayed")
    else:
        print("content is previously set. trying to click it")
        browser.find_element_by_id('$1_content_content').click()
        print("clicked")
        time.sleep(1)
        print("trying to clear it")
        browser.find_element_by_id('$1_content_content').clear()
        print("and now it is cleared")
    is_visible(browser, "$1_content_content")# 等待出现"1_content_content"
    browser.find_element_by_id('$1_content_content').click()
    print("content clicked")
    print("trying to modify content")
    browser.find_element_by_id('$1_content_content').send_keys(info)
    print("tried")
    print("content is now --* " + browser.find_element_by_id('$1_content_content').get_attribute('innerHTML') + " *--")
    print("trying to CTRL+Enter to send")
    browser.find_element_by_id('$1_content_content').send_keys(Keys.CONTROL, Keys.ENTER)
    print("it should have been sent")
    time.sleep(3)

    print("Done!!!")
    browser.quit()


attempts = 0
success = False
while attempts < 3 and not success:
    try:
        print("城市：" + windCity)
        msg = ""
        for i in range(int(re.search(r"(\d)级", getWindSpeed(windCity)).group(1))):
            msg = msg + "呼呼"
        msg = msg + "\n\n" + requests.get("https://v1.hitokoto.cn/?encode=text").text
        print("今日句子：\n" + msg)
        success = True
        Qzone(msg)
    except:
        print("出现错误正在重试...")
        attempts += 1
        if attempts == 3:
            print("超过重试次数 结束程序")
            break
