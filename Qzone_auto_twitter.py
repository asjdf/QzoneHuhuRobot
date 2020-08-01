import os
import time
import random
import json
import re
import datetime
import sys
import traceback
from io import BytesIO
from urllib.request import urlretrieve
import requests
import pickle
from PIL import Image
import cv2
import numpy as np
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import jieba
import jieba.analyse
import logging
from wordcloud import WordCloud
from dotenv import load_dotenv
import base64
import asyncio


def catch_exception(origin_func):
    def wrapper(self, *args, **kwargs):
        """
        用于异常捕获的装饰器
        :param origin_func:
        :return:
        """
        try:
            return origin_func(self, *args, **kwargs)
        except AssertionError as ae:
            print('参数错误：{}'.format(str(ae)))
        except NoSuchElementException as nse:
            print('匹配元素超时，超过{}秒依然没有发现元素：{}'.format(QzoneSpider.timeout, str(nse)))
        except TimeoutException:
            print(f'请求超时：{self.driver.current_url}')
        except UserWarning as uw:
            print('警告：{}'.format(str(uw)))
        except WebDriverException as wde:
            print(f'未知错误：{str(wde)}')
        except Exception as e:
            print('出错：{} 位置：{}'.format(str(e), traceback.format_exc()))
        finally:
            self.driver.quit()
            print('已关闭浏览器，释放资源占用')

    return wrapper


class QzoneSpider(object):
    # 超时秒数，包括隐式等待和显式等待
    timeout = 33

    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.129 Safari/537.36'

    # 匹配无效内容的正则
    invalid_val_regex = re.compile(r'&.*?;|<.*?>|\n|\[\w+\].*?\[/\w+\]')

    # 匹配汉字和英文
    real_val_regex = re.compile(r'^[\u4e00-\u9fa5]+|[A-Za-z]{3,}$')

    def __init__(self):
        # 加载环境变量
        load_dotenv(verbose=True, override=True, encoding='utf-8')

        self.options = webdriver.ChromeOptions()

        self.options.add_argument(f'user-agent={QzoneSpider.user_agent}')
        self.options.add_experimental_option('excludeSwitches', ['enable-automation'])
        self.options.add_experimental_option('useAutomationExtension', False)
        self.options.add_argument('--disable-extensions')  # 禁用扩展
        self.options.add_argument('--profile-directory=Default')
        self.options.add_argument('--incognito')  # 隐身模式
        self.options.add_argument('--disable-plugins-discovery')
        self.options.add_argument('--start-maximized')
        self.options.add_argument('--window-size=1366,768')

        self.options.add_argument('--headless')
        self.options.add_argument('--disable-gpu')  # 谷歌官方文档说加上此参数可减少 bug，仅适用于 Windows 系统

        # 解决 unknown error: DevToolsActivePort file doesn't exist
        self.options.add_argument('--no-sandbox')  # 绕过操作系统沙箱环境
        self.options.add_argument('--disable-dev-shm-usage')  # 解决资源限制，仅适用于 Linux 系统

        self.driver = webdriver.Chrome(options=self.options)
        self.driver.implicitly_wait(QzoneSpider.timeout)

        # 防止通过 window.navigator.webdriver === true 检测模拟浏览器
        # 参考：
        # https://www.selenium.dev/selenium/docs/api/py/webdriver_chrome/selenium.webdriver.chrome.webdriver.html#selenium.webdriver.chrome.webdriver.WebDriver.execute_cdp_cmd
        # https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-addScriptToEvaluateOnNewDocument
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })

        # 统配显式等待
        self.wait = WebDriverWait(self.driver, timeout=QzoneSpider.timeout, poll_frequency=0.5)

        self.cookies_file = 'cookies_jar'
        self.username = os.getenv('YOUR_QQ')
        self.password = os.getenv('PASSWORD')

        # QQ空间令牌
        self._g_tk = None

        self.cookies = None

    def __login(self, force=False):
        """
        登录 QQ 空间
        获取必要的 cookies 及令牌
        :param force: 是否强制登录，强制登录将忽略已存在的 cookies 文件，走完整登录逻辑
        :return:
        """
        if not force and os.path.exists(self.cookies_file):
            QzoneSpider.format_print('发现已存在 cookies 文件，免登录', 2)
            with open(self.cookies_file, 'rb') as f:
                self.cookies = pickle.load(f)
                self._g_tk = self.g_tk(self.cookies)

                return self.cookies, self._g_tk

        self.driver.get('https://qzone.qq.com/')

        login_frame = self.driver.find_element_by_id('login_frame')
        self.driver.switch_to.frame(login_frame)
        self.driver.find_element_by_id('switcher_plogin').click()

        u = self.driver.find_element_by_id('u')
        u.clear()
        self.send_keys_delay_random(u, self.username)

        time.sleep(2)

        p = self.driver.find_element_by_id('p')
        p.clear()
        self.send_keys_delay_random(p, self.password)

        self.driver.find_element_by_id('login_button').click()

        self.__fuck_captcha()

        # cookies 持久化
        cookies = {cookie['name']: cookie['value'] for cookie in self.driver.get_cookies()}
        with open(self.cookies_file, 'wb') as f:
            pickle.dump(cookies, f)

        self.cookies = cookies
        self._g_tk = self.g_tk(self.cookies)

        return self.cookies, self._g_tk

    @staticmethod
    def get_track(distance):
        """
        获取移动轨迹
        先加速再减速，滑过一点再反方向滑到正确位置，模拟真人
        :param distance:
        :return:
        """
        # 初速度
        v = 0

        # 单位时间为0.2s来统计轨迹，轨迹即0.2内的位移
        t = 0.1

        # 位移 / 轨迹列表，列表内的一个元素代表0.2s的位移
        tracks = []

        # 当前的位移
        curr_position = 0

        # 到达mid值开始减速
        mid = distance * 7 / 8

        # 先滑过一点，最后再反着滑动回来
        distance += 10

        while curr_position < distance:
            if curr_position < mid:
                # 加速度越小，单位时间的位移越小,模拟的轨迹就越多越详细
                a = random.randint(2, 4)  # 加速运动
            else:
                a = -random.randint(3, 5)  # 减速运动

            # 初速度
            v0 = v

            # 0.2秒时间内的位移
            s = v0 * t + 0.5 * a * (t ** 2)

            # 当前的位置
            curr_position += s

            # 添加到轨迹列表
            tracks.append(round(s))

            # 速度已经达到v,该速度作为下次的初速度
            v = v0 + a * t

        # 反着滑动到大概准确位置
        for i in range(4):
            tracks.append(-random.randint(2, 3))
        for i in range(4):
            tracks.append(-random.randint(1, 3))
        return tracks

    @staticmethod
    def get_distance_x(bg_block, slide_block):
        """
        获取滑块与缺口图块的水平距离
        :param bg_block:
        :param slide_block:
        :return:
        """
        image = cv2.imread(bg_block, 0)  # 带缺口的背景图
        template = cv2.imread(slide_block, 0)  # 缺口图块

        # 图片置灰
        tmp_dir = './images/tmp/'
        os.makedirs(tmp_dir, exist_ok=True)
        image_gray = os.path.join(tmp_dir, 'bg_block_gray.jpg')
        template_gray = os.path.join(tmp_dir, 'slide_block_gray.jpg')
        cv2.imwrite(image_gray, template)
        cv2.imwrite(template_gray, image)
        image = cv2.imread(template_gray)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        image = abs(255 - image)
        cv2.imwrite(template_gray, image)

        # 对比两图重叠区域
        image = cv2.imread(template_gray)
        template = cv2.imread(image_gray)
        result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
        y, x = np.unravel_index(result.argmax(), result.shape)

        return x

    def __is_visibility(self, locator: tuple) -> bool:
        """
        判断元素是否存在且可见
        :param locator: 定位器
        :return:
        """
        try:
            return bool(self.wait.until(EC.visibility_of_element_located(locator)))
        except Exception as e:
            return False

    def __fuck_captcha(self, max_retry_num=6):
        """
        模拟真人滑动验证
        :param max_retry_num: 最多尝试 max_retry_num 次
        :return:
        """
        # 判断是否出现滑动验证码
        QzoneSpider.row_print('正在检查是否存在滑动验证码...')
        if not self.__is_visibility((By.ID, 'newVcodeArea')):
            QzoneSpider.row_print('无滑动验证码，直接登录')

            return

        QzoneSpider.row_print('发现滑动验证码，正在验证...')

        # 切换到验证码 iframe
        self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'tcaptcha_iframe')))
        time.sleep(0.2)  # 切换 iframe 会有少许延迟，稍作休眠

        for i in range(1, max_retry_num + 1):
            # 背景图
            bg_block = self.wait.until(EC.visibility_of_element_located((By.ID, 'slideBg')))
            bg_img_width = bg_block.size['width']
            bg_img_x = bg_block.location['x']
            bg_img_url = bg_block.get_attribute('src')

            # 滑块图
            slide_block = self.wait.until(EC.visibility_of_element_located((By.ID, 'slideBlock')))
            slide_block_x = slide_block.location['x']
            slide_img_url = slide_block.get_attribute('src')

            # 小滑块
            drag_thumb = self.wait.until(EC.visibility_of_element_located((By.ID, 'tcaptcha_drag_thumb')))

            # 下载背景图和滑块图
            os.makedirs('./images/', exist_ok=True)
            urlretrieve(bg_img_url, './images/bg_block.jpg')
            urlretrieve(slide_img_url, './images/slide_block.jpg')

            # 获取图片实际宽度的缩放比例
            bg_real_width = Image.open('./images/bg_block.jpg').width
            width_scale = bg_real_width / bg_img_width

            # 获取滑块与缺口的水平方向距离
            distance_x = self.get_distance_x('./images/bg_block.jpg', './images/slide_block.jpg')
            real_distance_x = distance_x / width_scale - (slide_block_x - bg_img_x) + 4

            # 获取移动轨迹
            track_list = self.get_track(real_distance_x)

            # 按住小滑块不放
            ActionChains(self.driver).click_and_hold(on_element=drag_thumb).perform()
            time.sleep(0.2)

            # 分段拖动小滑块
            for track in track_list:
                ActionChains(self.driver).move_by_offset(xoffset=track, yoffset=0).perform()  # 将鼠标移动到当前位置 (x, y)
                time.sleep(0.002)
            time.sleep(1)

            # 放开小滑块
            ActionChains(self.driver).release(on_element=drag_thumb).perform()
            time.sleep(5)  # 跳转需要时间

            # 判断是否通过验证
            if 'user' in self.driver.current_url:
                QzoneSpider.row_print('已通过滑动验证', 1)
                self.driver.switch_to.default_content()

                return True
            else:
                QzoneSpider.row_print(f'滑块验证不通过，正在进行第 {i} 次重试...')
                self.wait.until(EC.element_to_be_clickable((By.ID, 'e_reload'))).click()
                time.sleep(0.2)

        raise UserWarning(f'滑块验证不通过，共尝试{max_retry_num}次')

    @staticmethod
    def g_tk(cookies: dict) -> int:
        """
        生成 QQ 空间令牌
        :param cookies:
        :return:
        """
        h = 5381
        s = cookies.get('p_skey', None) or cookies.get('skey', None) or ''
        for c in s:
            h += (h << 5) + ord(c)

        return h & 0x7fffffff

    @staticmethod
    def row_print(string, sleep_time=0.02):
        """
        在同一行输出字符
        :param string: 原始字符串
        :param sleep_time: 休眠秒数
        :return:
        """
        print('\r[{}] {}'.format(QzoneSpider.now(), string), flush=True, end='')

        time.sleep(sleep_time)
    
    @staticmethod
    def now():
        """
        当前时间
        精确到毫秒
        :return:
        """
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    @staticmethod
    def row_print(string, sleep_time=0.02):
        """
        在同一行输出字符
        :param string: 原始字符串
        :param sleep_time: 休眠秒数
        :return:
        """
        print('\r[{}] {}'.format(QzoneSpider.now(), string), flush=True, end='')

        time.sleep(sleep_time)

    @staticmethod
    def format_print(string, sleep_time=0):
        print('\n[{}] {}'.format(QzoneSpider.now(), string), flush=True, end='')

        sleep_time and time.sleep(sleep_time)

    @staticmethod
    def now():
        """
        当前时间
        精确到毫秒
        :return:
        """
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    def send_keys_delay_random(self, element, keys, min_delay=0.13, max_delay=0.52):
        """
        随机延迟输入
        :param element:
        :param keys:
        :param min_delay:
        :param max_delay:
        :return:
        """
        for key in keys:
            element.send_keys(key)
            time.sleep(random.uniform(min_delay, max_delay))

    def __post(self,msg):
        params = {
            'syn_tweet_verson': '1',
            'paramstr': '1',
            'pic_template': '',
            'richtype': '',
            'richval': '',
            'special_url': '',
            'subrichtype': '',
            'who': '1',
            'con': msg,
            'feedversion': '1',
            'ver': '1',
            'ugc_right': '1',
            'to_sign': '0',
            'hostuin': self.username,
            'code_version': '1',
            'format': 'fs',
            'qzreferrer': 'https://user.qzone.qq.com/' + self.username
        }
        headers = {
            'user-agent': QzoneSpider.user_agent,
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7,und;q=0.6',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
        }
        pUrl = 'https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/emotion_cgi_publish_v6?&g_tk=' + str(self._g_tk)
        response = requests.post(pUrl, data=params, headers=headers, cookies=self.cookies)
        print('1')
        # print(re.findall(r"frameElement.callback\((.+?)\); </script></body>", response.text)[0])
        msg_data = json.loads(re.findall(r"frameElement.callback\((.+?)\); </script></body>", response.text)[0])
        code = msg_data['code']
        print(code)
        if code == -3000:
            print('由于之前缓存的 cookies 文件已失效，将尝试自动重新登录...')
            self.__login(force=True)
            return self.__post(msg)
        elif code != 0:
            raise Exception(msg_data['message'])

    def __post_pic(self,msg,pics = []):
        headers = {
            'user-agent': QzoneSpider.user_agent,
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7,und;q=0.6',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
        }
        imgUploadRe = []# 记录图片上传的应答
        for pic in pics:
            # print(pic)
            params = {
                'filename': 'filename',
                'uin': self.username,
                'skey': self.cookies['skey'],
                'zzpaneluin': self.cookies['ptui_loginuin'],
                'zzpanelkey': '',
                'p_uin': self.cookies['ptui_loginuin'],
                'p_skey': self.cookies['p_skey'],
                'qzonetoken': '',
                'uploadtype': '1',
                'albumtype': '7',
                'exttype': '0',
                'refer': 'shuoshuo',
                'output_type': 'jsonhtml',
                'charset': 'utf-8',
                'output_charset': 'utf-8',
                'upload_hd': '1',
                'hd_width': '2048',
                'hd_height': '10000',
                'hd_quality': '96',
                'url': 'https://up.qzone.qq.com/cgi-bin/upload/cgi_upload_image?g_tk=' + str(self._g_tk) ,
                'base64': '1',
                'jsonhtml_callback': 'callback',
                'picfile': pic
            }
            pUrl = 'https://up.qzone.qq.com/cgi-bin/upload/cgi_upload_image?g_tk=' + str(self._g_tk) + '&&g_tk='+ str(self._g_tk)
            # print(params)
            # print(pUrl)
            response = requests.post(pUrl, data=params, headers=headers, cookies=self.cookies)
            print(response.text)
            msg_data = json.loads(re.findall(r"frameElement.callback\((.+?)\);</script></body></html>", response.text)[0])
            print(msg_data)
            if 'ret' in msg_data['data']:
                code = msg_data['data']['ret']
            elif 'ret' in msg_data:
                code = msg_data['ret']
            else:
                print(查找code出错)
            print(code)
            if code == -100:
                print('由于之前缓存的 cookies 文件已失效，将尝试自动重新登录...')
                self.__login(force=True)
                return self.__post_pic(msg,pics = pics)
            elif code != 0:
                raise Exception(msg_data['data']['msg'])

            print(response.text)
            data = json.loads(re.findall(r"frameElement.callback\((.+?)\);</script></body>", response.text)[0])
            imgUploadRe.append(data)
        
        richval = ''
        bos = ''
        picNum = 0
        # 图片上传的richval和bos处理
        for data in imgUploadRe:
            picNum = picNum + 1
            richval = richval + ','+data['data']['albumid']+','+data['data']['lloc']+','+data['data']['sloc']+','+str(data['data']['type'])+','+str(data['data']['height'])+','+str(data['data']['width'])+',,'+str(data['data']['height'])+','+str(data['data']['width']) + '	'
            bos = bos +  re.findall(r"bo=(.+?)$", data['data']['url'])[0] + ','
        richval = richval.rstrip()
        bos = bos.rstrip(',')
        print(richval)
        print(bos)
        # picTemplate处理
        if picNum == 1:
            pic_template = ''
        else:
            pic_template = 'tpl-' + str(picNum) + '-1'
        params2 = {
            'syn_tweet_verson': '1',
            'paramstr': '1',
            'pic_template': pic_template,
            'richtype': '1',
            'richval': richval,
            'pic_bo': bos + '	' + bos,
            'special_url': '',
            'subrichtype': '1',
            'who': '1',
            'con': msg,
            'feedversion': '1',
            'ver': '1',
            'ugc_right': '1',
            'to_sign': '0',
            'hostuin': self.username,
            'code_version': '1',
            'format': 'fs',
            'qzreferrer': 'https://user.qzone.qq.com/' + self.username
        }
        print(params2)
        pUrl2 = 'https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/emotion_cgi_publish_v6?&g_tk=' + str(self._g_tk)
        r = requests.post(pUrl2, data=params2, headers=headers, cookies=self.cookies)
        print(r)
        print(r.content)
        return 1

    @catch_exception
    def run(self):
        self.__login()

    @catch_exception
    def pMsg(self, msg = 'none message'):
        self.__login()
        self.__post(msg)
        return 1

    @catch_exception
    def pImg(self, msg = 'none message',pic = []):
        self.__login()
        self.__post_pic(msg,pic)
        return 1


if __name__ == '__main__':
    spider = QzoneSpider()
    # spider.pMsg(msg = 'test')
    picCache = []
    img = Image.open('./headPic.jpg')
    output_buffer = BytesIO()
    img.save(output_buffer, format='JPEG')
    byte_data = output_buffer.getvalue()
    base64_str = base64.b64encode(byte_data)
    picCache.append(base64_str)
    img = Image.open('B:/Users/At/Desktop/_DSC1311.jpg')
    output_buffer = BytesIO()
    img.save(output_buffer, format='JPEG')
    byte_data = output_buffer.getvalue()
    base64_str = base64.b64encode(byte_data)
    picCache.append(base64_str)
    spider.pImg(msg = ' ',pic = picCache)
    