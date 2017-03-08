# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import ssl
import json
import urllib
import urllib2
import hashlib
import logging
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

from ice import DataIce


logger = logging.getLogger('DTS')

if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context


class Icein(object):

    def ice_init(self):
        self.dataice = DataIce()
        try:
            self.dataice.initialize()
        except Exception as e:
            return False
        return True

    def destroy(self):
        self.dataice.destroy()

    def get_data(self, data, modal):
        result = self.dataice.get_data(data, modal)
        return result
 

class Hxin(object):
    """画像接口"""
    login_url = 'https://api.100credit.cn/bankServer2/user/login.action'
    query_url = 'https://api.100credit.cn/bankServer2/data/terData.action'
    haina_api_url = 'http://192.168.22.27:8081/HainaApi/data/getData.action'

    def __init__(self, username, password, apicode):
        super(Hxin, self).__init__()
        self.username = username
        self.password = password
        self.apicode = apicode
        self.tokenid = None

    @staticmethod
    def __post(url, data):
        """发送post请求"""
        req = urllib2.Request(url)
        data = urllib.urlencode(data)
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        resp = opener.open(req, data)
        res = resp.read()
        opener.close()
        return res

    @staticmethod
    def __getMd5Value(val):
        """将指定的val字符串转化为md5值"""
        md5 = hashlib.md5()
        md5.update(val)
        md5_val = md5.hexdigest()
        return md5_val

    def get_tokenid(self):
        """获取tokenid"""
        resjson = self.__post(self.login_url, {"userName": self.username,
                                               "password": self.password,
                                               "apiCode": self.apicode})
        res = json.loads(resjson)
        if res['code'] != '00':
            return False, self.apicode

        self.tokenid = res['tokenid']
        return True, ''

    def get_data(self, params, modal):
        """获取返回json"""
        if len(modal) == 1 and modal[0][1:] in ['TelCheck', 'IdPhoto', 'TelPeriod', 'TelStatus']:
            url = self.haina_api_url
            if 'bank_card1' in params.keys():
                params['bank_id'] = params['bank_card1']
            if 'bank_card2' in params.keys():
                params['bank_id'] = params['bank_card2']
            params['meal'] = modal[0]
        else:
            url = self.query_url
            if 'cell' in params.keys():
                params['cell'] = [params['cell']]
            if 'mail' in params.keys():
                params['mail'] = [params['mail']]
            if 'bank_card1' in params.keys():
                params['bank_id'] = params['bank_card1']
            if 'bank_card2' in params.keys():
                params['bank_id'] = params['bank_card2']
            params['meal'] = ','.join(modal)

        checkCode = self.__getMd5Value(json.dumps(params) + self.__getMd5Value(self.apicode + self.tokenid))
        data = {
            "tokenid": self.tokenid,
            "jsonData": json.dumps(params),
            "checkCode": checkCode,
            "apiCode": self.apicode
        }
        try:
            res = self.__post(url, data)
        except Exception:
            logger.exception('请求画像异常')
            res = '{}'
        return res
