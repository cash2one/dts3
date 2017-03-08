# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import Ice
import neo

CONF = {
    # 'Ice.Default.Locator': 'BrIceGrid/Locator:tcp -h 192.168.162.181 -p 4061:tcp -h 192.168.162.182 -p 4061',  # 测试
    'Ice.Default.Locator': 'BrIceGrid/Locator:tcp -h 192.168.23.111 -p 4061:tcp -h 192.168.23.112 -p 4061',  # 预发布
    'Ice.ThreadPool.Client.Size': '20',
    'Ice.ThreadPool.Client.SizeMax': '100',
    'Ice.Override.ConnectTimeout': '10000',
    'Ice.RetryIntervals': '0 1000 5000',
}
ID = 'NeoServiceV1.0.0'


class Neo(object):

    def __init__(self):
        props = Ice.createProperties()
        for k, v in CONF.items():
            props.setProperty(k, v)
        init_data = Ice.InitializationData()
        init_data.properties = props
        self.communicator = Ice.initialize(init_data)
        self.proxy = None

    def initialize(self):
        base = self.communicator.stringToProxy(ID)
        try:
            # 创建一个代理, 询问服务器是不是设定接口的代理, 是->proxy, 不是->none
            self.proxy = neo.NeoServicePrx.checkedCast(base)
        except Ice.ConnectTimeoutException:
            raise RuntimeError("Ice::ConnectTimeoutException")
        if not self.proxy:
            raise RuntimeError("Invalid proxy")

    def searchRelationship(self, jsonString, appKey):
        return self.proxy.searchRelationship(jsonString, appKey)

    def searchNodes(self, id_num):
        info1 = {
            "max_depth": "3",
            "max_count": "10",
            "cur_date": "0",
            "neo_cluster": "nc1",
            "cache_status": "1",
            "isPlaintext": "2",
            "appName": "DTS",
            "match": {"id": [id_num]}
        }
        info2 = {
            "max_depth": "3",
            "max_count": "10",
            "cur_date": "0",
            "neo_cluster": "nc2",
            "cache_status": "1",
            "isPlaintext": "2",
            "appName": "DTS",
            "match": {"id": [id_num]}
        }
        jsonString1 = json.dumps(info1)
        jsonString2 = json.dumps(info2)

        res1 = self.proxy.searchNodes(jsonString1, '')
        res2 = self.proxy.searchNodes(jsonString2, '')
        res = json.loads(res1.data) + json.loads(res2.data)
        if len(res) == 2:
            val1 = json.loads(res[0])
            val2 = json.loads(res[1])
            val1['list'] = val1['list'] + val2['list']
            res = json.dumps([json.dumps(val1)])
        else:
            res = json.dumps(res)
        return res

    def destroy(self):
        if self.communicator:
            self.communicator.destroy()


if __name__ == "__main__":
    l = Neo()
    dic = {
        "max_depth": "3",
        "max_count": "10",
        "cur_date": "0",
        "neo_cluster": "",
        "cache_status": "1",
        "isPlaintext": "2",
        "appName": "DTS",
        "match": {"id": []}
    }
    jsonString = json.dumps(dic)
    appKey = 'S1007'

    l.initialize()
    res = l.searchNodes("110226198309260529")   
    print res, type(res)
    l.destroy()
