# -*- coding:utf-8 -*-
from __future__ import absolute_import
import os
import csv
import json
import random
import time
import codecs
import threading
import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from django.core.files import File
from django.contrib.auth.models import User

from celery import current_app as app

from DTS.views import send_mail
from account.models import Member
from customer.models import SourceFile
from analyst.mapinter import Hxin, Icein
from analyst.models import Interface, MappingedFile, WTasks
from analyst.utils import FileReader, redisconn


logger = logging.getLogger('DTS')
RDS = redisconn()
TMP_PATH = settings.TMP_PATH


class MappingWorker(threading.Thread):
    def __init__(self, func, modal, key, cus_username):
        super(MappingWorker, self).__init__()
        self.setDaemon(1)
        self._func = func
        self._md = modal
        self._rds = RDS
        self._key = key
        self._res = key+'_res'
        self._cus_username = cus_username  # 客户用户名

    def run(self):
        while self._rds.exists(self._key):
            line = self._rds.lpop(self._key)
            res = self._func(line, self._md, self._cus_username)
            self._rds.lset(self._res, res['num'], json.dumps(res))


def build_worker_pool(func, modal, redis_data_key, cus_username, size=10):
    workers = []
    for _ in xrange(size):
        worker = MappingWorker(func, modal, redis_data_key, cus_username)
        worker.start()
        workers.append(worker)
    return workers


def encrypt(que_line):
    """脱敏"""
    if 'id' in que_line:
        if len(que_line['id']) > 14:
            que_line['id'] = que_line['id'][:-4]+'##'+que_line['id'][-2]+'#'
    if 'name' in que_line:
        que_line['name'] = '####'
    if 'cell' in que_line:
        if len(que_line['cell']) == 11:
            que_line['cell'] = que_line['cell'][0][:-4] + '####'
    if 'bank_card2' in que_line:
        if len(que_line['bank_card2']) > 14:
            que_line['bank_card2'] = que_line['bank_card2'][:12] + '#'*(len(que_line['bank_card2'][12:]) - 1) + que_line['bank_card2'][-1:]
    if 'bank_card1' in que_line:
        if len(que_line['bank_card1']) > 14:
            que_line['bank_card1'] = que_line['bank_card1'][:12] + '#'*(len(que_line['bank_card1'][12:]) - 1) + que_line['bank_card1'][-1:]
    if 'email' in que_line:
        if '@' in que_line['email']:
            pos = que_line['email'].find('@')
            if pos >= 0:
                que_line['email'] = '####' + que_line['email'][0][pos:]
    return que_line


@app.task(name='taskfor_hx')
def for_hx(rediskey, fileid, memberid, modal, cus_username):
    member = get_object_or_404(Member, pk=memberid)
    qer = member.queryer
    username = member.user.username

    hxobj = Hxin(qer.username, qer.password, qer.apicode)
    status, msg = hxobj.get_tokenid()
    if not status:
        send_mail([member.user.email, 'yu.zhao@100credit.com', 'lei.zhang1@100credit.com'],
                  '百融数据测试管理系统', '<p>%s画像账号错误登陆失败,请联系相关工作人员检查！</p>' % qer.apicode)
        qer.is_busy = False
        qer.taskid = ''
        qer.mapinter = ''
        qer.fileid = None
        qer.end_time = timezone.now()
        qer.save()
        return None

    def process_line(line, modal, cus_username):
        que_line = json.loads(line)
        que_line['swift_number'] = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
        que_line['cus_username'] = cus_username
        num = int(que_line['cus_num']) - 1
        info = que_line.copy()

        resjson = hxobj.get_data(info, modal)
        res_dic = json.loads(resjson)
        data_txt = json.dumps(info) + '\t\t' + ','.join(modal) + '\t\t' + resjson + '\n'

        que_line = encrypt(que_line)  # 脱敏
        res_dic.update(que_line)
        return {"res_dic": res_dic, "data_txt": data_txt, "num": num}

    workers = build_worker_pool(process_line, modal, rediskey, cus_username)
    for worker in workers:
        worker.join()

    return username + '_res'  # 这是匹配结果的redis key


@app.task(name='export_hx_result_to_file', ignore_result=True)
def export_hx_result_to_file(redis_result_key, fileid, memberid, modal):
    """
    将redis中存储的匹配结果, 导出为文件.
    注意: 此任务的worker只在部署web的服务器上启动一个 即: --concurrency=1
    """
    if redis_result_key is None or not RDS.exists(redis_result_key):
        logger.info('export_hx_result_to_file: %s is not exists' % redis_result_key)
        return

    member = get_object_or_404(Member, pk=memberid)
    qer = member.queryer
    file = get_object_or_404(SourceFile, pk=fileid)

    filehead = file.fields + ",swift_number," + ','.join([obj.filehead for obj in Interface.objects.filter(name__in=modal)])
    filename, _ = os.path.splitext(os.path.basename(file.filename.path))
    mapinter = ','.join([inter.alias for inter in Interface.objects.filter(name__in=modal)])

    f_csv = open(TMP_PATH+filename+'.csv', 'w')
    f_csv.write(codecs.BOM_UTF8)
    f_txt = open(TMP_PATH+filename+'.txt', 'w')
    f_txt.write(codecs.BOM_UTF8)

    csvfile = csv.DictWriter(f_csv, filehead.split(','), delimiter=',')
    csvfile.writeheader()

    while RDS.exists(redis_result_key):
        content = json.loads(RDS.lpop(redis_result_key))
        csvfile.writerow(content['res_dic'])
        f_txt.write(content['data_txt'])

    f_csv.close()
    f_txt.close()

    csv_obj = File(open(TMP_PATH+filename+'_res_'+str(file.id)+'.csv'))
    MappingedFile.objects.create(source_file=file, member=member, file=csv_obj,
                                 file_size=csv_obj.size, mapinter=mapinter)
    csv_obj.close()

    txt_obj = File(open(TMP_PATH+filename+'_res_'+str(file.id)+'.txt'))
    MappingedFile.objects.create(source_file=file, member=member, file=txt_obj,
                                 file_size=txt_obj.size, mapinter=mapinter)
    txt_obj.close()

    qer.is_busy = False
    qer.taskid = ''
    qer.mapinter = ''
    qer.fileid = None
    qer.end_time = timezone.now()
    qer.save()

    send_mail([member.user.email], '百融数据测试管理系统', '<p>文件:%s 匹配完成</p>' % filename)


def make_task_hx(rediskey, fileid, memberid, modal, cus_username):
    chain = for_hx.s(rediskey, fileid, memberid, modal, cus_username) | export_hx_result_to_file.s(fileid, memberid, modal)
    chain()


class IceWorker(threading.Thread):
    def __init__(self, func, modal, key, iceobj, cus_username):
        super(IceWorker, self).__init__()
        self.setDaemon(1)
        self._func = func
        self._md = modal
        self._rds = RDS
        self._key = key
        self._res = key+'_res'
        self._iceobj = iceobj
        self._cus_username = cus_username

    def run(self):
        while self._rds.exists(self._key):
            line = self._rds.lpop(self._key)
            res = self._func(line, self._md, self._iceobj, self._key, self._cus_username)
            self._rds.lset(self._res, res['num'], json.dumps(res))


def build_iceworker_pool(func, modal, redis_data_key, size, iceobj, cus_username):
    workers = []
    for _ in xrange(size):
        worker = IceWorker(func, modal, redis_data_key, iceobj, cus_username)
        worker.start()
        workers.append(worker)
    return workers


@app.task(name='taskfor_ice')
def for_ice(rediskey, fileid, memberid, modal, cus_username):
    member = get_object_or_404(Member, pk=memberid)
    file = get_object_or_404(SourceFile, pk=fileid)
    qer = member.queryer

    iceobj = Icein()
    status = iceobj.ice_init()
    if not status:
        send_mail([member.user.email, 'yu.zhao@100credit.com', 'lei.zhang1@100credit.com'],
                  '百融数据测试管理系统', '<p>ice服务异常,请联系相关工作人员检查！</p>')
        qer.is_busy = False
        qer.taskid = ''
        qer.mapinter = ''
        qer.fileid = None
        qer.end_time = timezone.now()
        qer.save()
        return False, 'ice init error!'

    filename, _ = os.path.splitext(os.path.basename(file.filename.path))
    inter = Interface.objects.get(name=modal[0])
    size = inter.thread_num

    workers = build_iceworker_pool(switch[modal[0][1:]], modal, rediskey, size, iceobj, cus_username)
    for worker in workers:
        worker.join()

    iceobj.destroy()
    return member.user.username + '_res'


@app.task(name='export_ice_result_to_file', ignore_result=True)
def export_ice_result_to_file(redis_result_key, fileid, memberid, modal):
    """
    将redis中存储的匹配结果, 导出为文件.
    """
    if redis_result_key is None or not RDS.exists(redis_result_key):
        logger.info('export_ice_result_to_file: %s is not exists' % redis_result_key)
        return

    member = get_object_or_404(Member, pk=memberid)
    username = member.user.username
    file = get_object_or_404(SourceFile, pk=fileid)
    filename, _ = os.path.splitext(os.path.basename(file.filename.path))
    qer = member.queryer
    inter = Interface.objects.get(name=modal[0])
    mapinter = inter.alias
    filehead = file.fields + ",swift_number," + inter.filehead

    f_csv = open(TMP_PATH+filename+'.csv', 'w')
    f_csv.write(codecs.BOM_UTF8)
    f_txt = open(TMP_PATH+filename+'.txt', 'w')
    f_txt.write(codecs.BOM_UTF8)

    csvfile = csv.DictWriter(f_csv, filehead.split(','), delimiter=',')
    csvfile.writeheader()

    while RDS.exists(redis_result_key):
        content = json.loads(RDS.lpop(username + '_res'))
        csvfile.writerow(content['res_dic'])
        f_txt.write(content['data_txt'])

    f_csv.close()
    f_txt.close()

    csv_obj = File(open(TMP_PATH+filename+'_res_'+str(file.id)+'.csv'))
    MappingedFile.objects.create(source_file=file, member=member, file=csv_obj,
                                 file_size=csv_obj.size, mapinter=mapinter)
    csv_obj.close()

    txt_obj = File(open(TMP_PATH+filename+'_res_'+str(file.id)+'.txt'))
    MappingedFile.objects.create(source_file=file, member=member, file=txt_obj,
                                 file_size=txt_obj.size, mapinter=mapinter)
    txt_obj.close()

    qer.is_busy = False
    qer.taskid = ''
    qer.mapinter = ''
    qer.fileid = None
    qer.end_time = timezone.now()
    qer.save()


def make_task_ice(rediskey, fileid, memberid, modal, cus_username):
    chain = for_ice.s(rediskey, fileid, memberid, modal, cus_username) | export_ice_result_to_file.s(fileid, memberid, modal)
    chain()


@app.task(name='taskfor_scan')
def for_scan():
    wtasks = WTasks.objects.all()
    for t in wtasks:
        username = t.username
        modal = json.loads(t.modal)
        fileid = t.fileid
        user = User.objects.get(username=username)
        member = user.member
        qer = user.member.queryer
        if qer.is_busy:
            continue
        else:
            file = get_object_or_404(SourceFile, pk=fileid)
            file_obj = FileReader(file, username)
            if len(modal) == 1 and modal[0][0] == '1':
                filedata = file_obj.read_filedata()
                rediskey = file_obj.tansform_filedata(filedata)
                task = for_ice.delay(rediskey, file.id, member.id, modal)
            else:
                filedata = file_obj.read_filedata()
                rediskey = file_obj.tansform_filedata(filedata)
                task = for_hx.delay(rediskey, file.id, member.id, modal)
            qer.is_busy = True
            qer.mapinter = ','.join([inter.alias for inter in Interface.objects.filter(name__in=modal)])
            qer.fileid = file.id
            qer.start_time = timezone.now()
            qer.taskid = task.id
            qer.save()
            return 'add task to celery'


def hf_bankthree(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'realName': que_line['name'].strip(),
        'idCard': que_line['id'].strip(),
        'bankCard': que_line['bank_card1'].strip(),
        'client_type': '100002',
        'swift_number': swift_number
    }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    data = json.loads(rescls.data)
    if status == '0':
        # 打平
        res_dic.update({"code": '00'})
        res_dic.update({"costTime": data['costTime']})
        if 'data' in data:
            resCode = data['data'][0]['record'][0]['resCode']
        if resCode == '00':
            res_dic.update({'resCode': "00"})
        elif resCode == '06':
            res_dic.update({'resCode': "01"})
        elif resCode in ['01', '02', '03', '04', '05']:
            res_dic.update({'resCode': "10"})
        elif resCode in ['07', '09', '12', '13', '14', '15', '16', '17', '18', '19']:
            res_dic.update({'resCode': "11"})
        elif resCode in ['23', '98']:
            res_dic.update({'resCode': "20"})
        else:
            res_dic.update({'resCode': "99"})
    else:
        res_dic.update({'code': rescls.code})

    que_line = encrypt(que_line)  # 脱敏
    res_dic.update(que_line)
    data_txt = json.dumps(info) + '\t\t' + ','.join(modal) + '\t\t' + rescls.data + '\n'
    return {"res_dic": res_dic, "data_txt": data_txt, "num": num}

switch = {
    "hf_bankthree": hf_bankthree
}
