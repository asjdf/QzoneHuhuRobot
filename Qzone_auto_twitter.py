import requests
import json
import re
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
windCity = "莆田"
qq = ''
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
    browser.find_element_by_id('aIcenter').click()
    time.sleep(5)
    print("we are in " + browser.title)
    print("wait 10s to complete loading page")
    time.sleep(10)
    if (browser.find_element_by_id('$1_content_content').get_attribute('innerHTML') == ""):
        print("trying to click substitutor")
        browser.find_element_by_id('$1_substitutor_content').click()
        print("clicked. Now substitutor_content not displayed and content_content displayed")
        time.sleep(3)
    else:
        print("content is previously set. trying to click it")
        browser.find_element_by_id('$1_content_content').click()
        print("clicked")
        time.sleep(2)
        print("trying to clear it")
        browser.find_element_by_id('$1_content_content').clear()
        print("and now it is cleared")
        time.sleep(2)
    browser.find_element_by_id('$1_content_content').click()
    print("content clicked")
    time.sleep(2)
    print("trying to modify content")
    browser.find_element_by_id('$1_content_content').send_keys(info)
    print("tried")
    time.sleep(3)
    print("content is now --* " + browser.find_element_by_id('$1_content_content').get_attribute('innerHTML') + " *--")
    time.sleep(3)
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
        print("出现错误正在重试..." + attempts)
        attempts += 1
        if attempts == 3:
            print("超过重试次数 结束程序")
            break
