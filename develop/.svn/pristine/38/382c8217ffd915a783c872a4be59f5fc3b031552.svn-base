#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import Ice
import dac

CONF = {
    # 'Ice.Default.Locator': 'BrIceGrid/Locator:tcp -h 192.168.23.111 -p 4061:tcp -h 192.168.23.112 -p 4061',  # 预发
    "Ice.Default.Locator": "DacIceGrid/Locator:tcp -h 192.168.22.58 -p 4061: default -h 192.168.22.59 -p 4061",
    'Ice.ThreadPool.Client.Size': '20',
    'Ice.ThreadPool.Client.SizeMax': '100',
    'Ice.Override.ConnectTimeout': '10000',
    'Ice.RetryIntervals': '0 1000 5000',
}
ID = 'DacServiceV1.0.0'


class DataIce(object):

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
            self.proxy = dac.DacServicePrx.checkedCast(base)
        except Ice.ConnectTimeoutException:
            raise RuntimeError("Ice::ConnectTimeoutException")
        if not self.proxy:
            raise RuntimeError("Invalid proxy")

    def get_data(self, info, modal):
        # TODO modal参数传递不合理
        if modal[0] in ["1zyhl_ydsj1", "1zyhl_ydsj2"]:
            result = self.proxy.getData(json.dumps(info), modal[0][1:-1])
        else:
            result = self.proxy.getData(json.dumps(info), modal[0][1:])
        return result or '{}'

    def destroy(self):
        if self.communicator:
            self.communicator.destroy()


if __name__ == '__main__':
    dataice = DataIce()
    dataice.initialize()

    info = {'phone': '15123934043',
            'queryid': '0000000100000',
            'swift_number': "zhaoyu_091273490875940387698",
            'client_type': "100002"}

    ret = dataice.get_data(info, ['1zyhl_ydsj2'])

    print ret, type(ret)
    dataice.destroy()
