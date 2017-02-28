# -*- coding:utf-8 -*-
from __future__ import absolute_import
import logging
import os
import csv
import json
import random
import time
import codecs
import threading
import traceback

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from django.core.files import File
from django.db import connection
from django.contrib.auth.models import User

from celery import current_app as app

from DTS.views import send_mail
from account.models import Member
from customer.models import SourceFile
from analyst.mapinter import Hxin, Icein
from analyst.models import Interface, MappingedFile, WTasks
from analyst.utils import FileReader, redisconn, is_connection_usable


logger = logging.getLogger('DTS')
conn = redisconn()
TMP_PATH = settings.TMP_PATH


class MappingWorker(threading.Thread):
    def __init__(self, func, modal, key, cus_username):
        super(MappingWorker, self).__init__()
        self.setDaemon(1)
        self._func = func
        self._md = modal
        self._rds = conn
        self._key = key
        self._res = key+'_res'
        self._cus_username = cus_username  # 客户用户名

    def run(self):
        while self._rds.exists(self._key):
            line = self._rds.lpop(self._key)
            res = self._func(line, self._md, self._cus_username)
            self._rds.lset(self._res, res['num'], json.dumps(res))


def build_worker_pool(func, modal, redis_data_key, cus_username, size=1):
    workers = []
    for _ in xrange(size):
        worker = MappingWorker(func, modal, redis_data_key, cus_username)
        worker.start()
        workers.append(worker)
    return workers

def deal(que_line):
    if 'id' in que_line.keys():
        if len(que_line['id']) > 14:
            que_line['id'] = que_line['id'][:-4]+'##'+que_line['id'][-2]+'#'
    if 'name' in que_line.keys():
        que_line['name'] = '####'
    if 'cell' in que_line.keys():
        if len(que_line['cell']) == 11:
            que_line['cell'] = que_line['cell'][0][:-4] + '####'
    if 'bank_card2' in que_line.keys():
        if len(que_line['bank_card2']) > 14:
            que_line['bank_card2'] = que_line['bank_card2'][:12] + '#'*(len(que_line['bank_card2'][12:]) -1) + que_line['bank_card2'][-1:]
    if 'bank_card1' in que_line.keys():
        if len(que_line['bank_card1']) > 14:
            que_line['bank_card1'] = que_line['bank_card1'][:12] + '#'*(len(que_line['bank_card1'][12:]) -1) + que_line['bank_card1'][-1:]
    if 'email' in que_line.keys():
        if '@' in que_line['email']:
            pos = que_line['email'].find('@')
            if pos >= 0:
                que_line['email'] = '####' + que_line['email'][0][pos:]


@app.task(name='taskfor_hx')
def for_hx(rediskey, fileid, memberid, modal, cus_username):
    if not is_connection_usable():
        connection.close()
    member = get_object_or_404(Member, pk=memberid)
    file = get_object_or_404(SourceFile, pk=fileid)
    qer = member.queryer

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
        return False, 'apicode log in error!'

    def process_line(line, modal, cus_username):
        que_line = json.loads(line)
        que_line['cus_username'] = cus_username
        num = int(que_line['cus_num']) - 1
        info = que_line.copy()

        resjson = hxobj.get_data(info, modal)
        res_dic = json.loads(resjson)
        txt_dic = res_dic.copy()
        deal(que_line)
        txt_dic.update({"info":que_line,"interface":','.join(modal)})
        res_dic.update(que_line)
        if modal[0] in ['TelCheck', 'TelPeriod', 'TelStatus']:
            if res_dic['code'] == 600000:
                res_dic.update({'operation': res_dic['product']['operation'], 'result': res_dic['product']['result'], 'costTime': res_dic['product']['costTime']})
                if modal[0] == "TelCheck":
                    res_dic.update({'flag_telCheck': res_dic['flag']['flag_telCheck']})
                elif modal[0] == "TelPeriod":
                    res_dic.update({'flag_telCheck': res_dic['flag']['flag_telperiod']})
                elif modal[0] == "TelStatus":
                    res_dic.update({'flag_telCheck': res_dic['flag']['flag_telstatus']})
                res_dic.pop('product')
                res_dic.pop('flag')
        return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}

    a = []
    for s in modal:
        if s in ['scorep2p','brcreditpointv2','scorelargecashv1','scoreconsoff','scoreconsoffv2','ScoreCust','bankpfbebepoint','DataCust','scoepettycashv1','scorecreditbt','scorelargecashv2','scorecf']:
            a.append(s)
    if a:
        filehead = file.fields + ",swift_number,cus_username,code,flag_score," + ','.join([obj.filehead for obj in Interface.objects.filter(name__in=modal)])
    else:
        filehead = file.fields + ",swift_number,cus_username,code," + ','.join([obj.filehead for obj in Interface.objects.filter(name__in=modal)])
    
    filename, _ = os.path.splitext(os.path.basename(file.filename.path))
    mapinter = ','.join([inter.alias for inter in Interface.objects.filter(name__in=modal)])

    workers = build_worker_pool(process_line, modal, rediskey, cus_username)
    for worker in workers:
        worker.join()

    f_csv = open(TMP_PATH+filename+'_res_'+str(file.id)+'.csv', 'w')
    f_csv.write(codecs.BOM_UTF8)
    f_txt = open(TMP_PATH+filename+'_res_'+str(file.id)+'.txt', 'w')
    f_txt.write(codecs.BOM_UTF8)

    csvfile = csv.DictWriter(f_csv, filehead.split(','), delimiter=',')
    csvfile.writeheader()
    while conn.exists(member.user.username+'_res'):
        n = conn.lpop(member.user.username+'_res')
        content = json.loads(n)
        for key in content['res_dic'].keys():
            if key not in filehead.split(','):
                content['res_dic'].pop(key)
        csvfile.writerow(content['res_dic'])
        f_txt.write(json.dumps(content['data_txt'])+'\n')
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
    return True, 'success'


class IceWorker(threading.Thread):
    def __init__(self, func, modal, key, iceobj, cus_username):
        super(IceWorker, self).__init__()
        self.setDaemon(1)
        self._func = func
        self._md = modal
        self._rds = conn
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
    if not is_connection_usable():
        connection.close()
    member = get_object_or_404(Member, pk=memberid)
    file = get_object_or_404(SourceFile, pk=fileid)
    qer = member.queryer
    iceobj = Icein()
    status = iceobj.ice_init()
    if not status:
        send_mail([member.user.email,'yu.zhao@100credit.com','lei.zhang1@100credit.com'], '百融数据测试管理系统'
            , '<p>ice服务异常,请联系相关工作人员检查！</p>')
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
    mapinter = inter.alias

    filehead = file.fields + ",swift_number,cus_username,hncode," + inter.filehead
    workers = build_iceworker_pool(switch[modal[0][1:]], modal, rediskey, size, iceobj, cus_username)

    for worker in workers:
        worker.join()

    f_csv = open(TMP_PATH+filename+'_res_'+str(file.id)+'.csv', 'w')
    f_csv.write(codecs.BOM_UTF8)

    f_txt = open(TMP_PATH+filename+'_res_'+str(file.id)+'.txt', 'w')
    f_txt.write(codecs.BOM_UTF8)

    csvfile = csv.DictWriter(f_csv, filehead.split(','), delimiter=',')
    csvfile.writeheader()
    while conn.exists(member.user.username+'_res'):
        content = json.loads(conn.lpop(member.user.username+'_res'))
        for key in content['res_dic'].keys():
            if key not in filehead.split(','):
                content['res_dic'].pop(key)
        csvfile.writerow(content['res_dic'])
        f_txt.write(json.dumps(content['data_txt'])+'\n')

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
    iceobj.destroy()
    return True, 'success'


@app.task(name='taskfor_scan')
def for_scan():
    if not is_connection_usable():
        connection.close()
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
            cus_username = file.custom.user.username
            file_obj = FileReader(file,username)
            if len(modal) == 1 and modal[0][0] == '1':
                filedata = file_obj.read_filedata()
                rediskey = file_obj.tansform_filedata(filedata)
                task = for_ice.delay(rediskey, file.id, member.id, modal, cus_username)
            else:
                filedata = file_obj.read_filedata()
                rediskey = file_obj.tansform_filedata(filedata)
                task = for_hx.delay(rediskey, file.id, member.id, modal, cus_username)
            qer.is_busy = True
            qer.mapinter = ','.join([inter.alias for inter in Interface.objects.filter(name__in=modal)])
            qer.fileid = file.id
            qer.start_time = timezone.now()
            qer.taskid = task.id
            qer.save()
            t.delete()
            return 'add task to celery'
        

def hf_bankthree(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'realName': que_line['name'].strip(),
        'idCard':que_line['id'].strip(),
        'bankCard': que_line['bank_card1'].strip(),
        'client_type': '100002',
        'swift_number': swift_number
    }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        res_dic.update({"costTime": data['costTime']})
        if 'data' in data.keys():
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
        txt_dic = {"res":data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res":{}}

    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info,"interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def xb_xlxxcx(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'identity_name':que_line['name'].strip(),
        'identity_code': que_line['id'].strip(), 
        'client_type': '100002',
        'swift_number': swift_number
    }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        res_dic.update({"costTime": data['costTime']})
        code = data['api_status']["code"]
        api_status = data['api_status']
        if code == '000000' :
            res_dic.update({"code":code, "api_status":api_status['status'], 'description': api_status['description']})
            res_dic.update(data['data']['output'])
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}

    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info,"interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def zskj_idjy(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'idCard':que_line['id'],
        'name': que_line['name'],
        'client_type': '100002',
        'swift_number': swift_number
    }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        res_dic.update({"costTime": data['costTime']})
        if 'RESULT' in data.keys():
            RESULT = data['RESULT']
        else:
            RESULT = ''
        if 'guid' in data.keys():
            guid = data['guid']
        else:
            guid = ''
        res_dic.update({'RESULT': RESULT, 'guid': guid})
        txt_dic = {"res":data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res":{}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info,"interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def fh_perspre(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    if modal[1:] == 'fh_perspre':
        info = {'pname': que_line['name'].strip(),
                'client_type': '100002',
                'idcardNo':que_line['id'].strip(),
                'swift_number': swift_number}
    else:
        info = {'q': que_line['biz_name'].strip(),
                'client_type': '100002',
                'swift_number': swift_number}
    if 'other_var5' in que_line.keys():
        info.update({'datatype':que_line['other_var5']})
    if 'other_var1' in que_line.keys():
        info.update({'pageno':que_line['other_var1']})
    if 'other_var2' in que_line.keys():
        info.update({'range':que_line['other_var2']})

    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        q,w,e,r,a,s,d,f = 1,1,1,1,1,1,1,1
        res_dic.update({'code':data['code'],'costTime':data['costTime']})
        head = ["totalCount","pageNo","range",'msg']
        for key in head:
            if key in data.keys():
                res_dic.update({key:data[key]})
        if 'allList' in data.keys():
            for val in data['allList']:
                for k in val:
                    if val[k] and type(val[k])==type(u'sadf'):
                        if ';' in val[k]:
                            val.update({k:val[k].replace(';','')})
                if val['dataType'] == 'ktgg':
                    res_dic.update({'ktgg_sortTime'+str(q): val['sortTime'], 'ktgg_plaintiff'+str(q): val['plaintiff'], 'ktgg_organizer'+str(q): val['organizer']
                        ,'ktgg_courtroom'+str(q): val['courtroom'], 'ktgg_court'+str(q): val['court'], 'ktgg_title'+str(q): val['title']
                        ,'ktgg_caseCause'+str(q): val['caseCause'], 'ktgg_judge'+str(q): val['judge'], 'ktgg_caseNo'+str(q): val['caseNo']
                        ,'ktgg_defendant'+str(q): val['defendant'], 'ktgg_body'+str(q): val['body']})
                    if 'matchRatio' in val.keys():
                        res_dic.update({'ktgg_matchRatio'+str(q):val['matchRatio']})
                    q = q +1
                if val['dataType'] == 'ajlc':
                    res_dic.update({'ajlc_sortTime'+str(w):val['sortTime'], 'ajlc_member'+str(w): val['member'], 'ajlc_clerkPhone'+str(w): val['clerkPhone']
                        ,'ajlc_caseType'+str(w): val['caseType'],'ajlc_trialProcedure'+str(w):val['trialProcedure'], 'ajlc_sentencingDate'+str(w):val['sentencingDate']
                        ,'ajlc_status'+str(w): val['status'], 'ajlc_caseStatus'+str(w): val['caseStatus'], 'ajlc_organizer'+str(w): val['organizer']
                        ,'ajlc_filingDate'+str(w): val['filingDate'], 'ajlc_court'+str(w): val['court'], 'ajlc_ajlcStatus'+str(w): val['ajlcStatus']
                        ,'ajlc_chiefJudge'+str(w): val['chiefJudge'], 'ajlc_caseCause'+str(w): val['caseCause'], 'ajlc_trialLimitDate'+str(w): val['trialLimitDate']
                        ,'ajlc_clerk'+str(w): val['clerk'], 'ajlc_judge'+str(w): val['judge'], 'ajlc_actionObject'+str(w): val['actionObject']
                        ,'ajlc_pname'+str(w): val['pname'], 'ajlc_caseNo'+str(w): val['caseNo'], 'ajlc_effectiveDate'+str(w): val['effectiveDate']
                        ,'ajlc_body'+str(w): val['body']})
                    if 'matchRatio' in val.keys():
                        res_dic.update({'ajlc_matchRatio'+str(q):val['matchRatio']})
                    w = w + 1
                if val['dataType'] == 'wdhmd':
                    res_dic.update({'wdhmd_updateTime'+str(e): val['updateTime'], 'wdhmd_sortTime'+str(e): val['sortTime']
                        ,'wdhmd_execCourt'+str(e): val['execCourt'], 'wdhmd_whfx'+str(e): val['whfx'], 'wdhmd_bjbx'+str(e): val['bjbx'], 'wdhmd_caseCode'+str(e): val['caseCode']
                        ,'wdhmd_sourceName'+str(e): val['sourceName'], 'wdhmd_datasource'+str(e): val['datasource'], 'wdhmd_yhje'+str(e):val['yhje'], 'wdhmd_body'+str(e):val['body']})
                    if 'matchRatio' in val.keys():
                        res_dic.update({'wdhmd_matchRatio'+str(q):val['matchRatio']})
                    if 'age' in val.keys():
                        res_dic.update({'wdhmd_age'+str(e):val['age'], 'wdhmd_pname'+str(e): val['pname'], 'wdhmd_sex'+str(e):val['sex'],'wdhmd_phone'+str(e):val['phone']
                            ,'wdhmd_idcardNo'+str(e):val['idcardNo'], 'wdhmd_birthPlace'+str(e): val['birthPlace'], 'wdhmd_address'+str(e): val['address']
                            ,'wdhmd_email'+str(e):val['email'], 'wdhmd_mobile'+str(e): val['mobile']})
                    e = e + 1 
                if val['dataType'] == 'cpws':
                    res_dic.update({'cpws_sortTime'+str(r):val['sortTime'],'cpws_caseType'+str(r):val['caseType'],'cpws_trialProcedure'+str(r):val['trialProcedure']
                        ,'cpws_court'+str(r):val['court'],'cpws_title'+str(r):val['title'],'cpws_judge'+str(r):val['judge']
                        ,'cpws_caseNo'+str(r):val['caseNo'],'cpws_judgeResult'+str(r):val['judgeResult'],'cpws_caseCause'+str(r):val['caseCause']
                        ,'cpws_yiju'+str(r):val['yiju'],'cpws_courtRank'+str(r):val['courtRank'],'cpws_body'+str(r):val['body']
                        })
                    if 'matchRatio' in val.keys():
                        res_dic.update({'cpws_matchRatio'+str(q):val['matchRatio']})
                    r = r + 1
                if val['dataType'] == 'zxgg':
                    res_dic.update({'zxgg_sortTime'+str(a):val['sortTime'], 'zxgg_title'+str(a):val['title'], 'zxgg_pname'+str(a): val['pname']
                        ,'zxgg_court'+str(a):val['court'],'zxgg_proposer'+str(a):val['proposer'],'zxgg_caseNo'+str(a):val['caseNo']
                        ,'zxgg_caseState'+str(a):val['caseState'],'zxgg_idcardNo'+str(a):val['idcardNo'],'zxgg_execMoney'+str(a):val['execMoney']
                        ,'zxgg_body'+str(a):val['body']})
                    a = a + 1
                if val['dataType'] == 'shixin':
                    res_dic.update({'shixin_sortTime'+str(s):val['sortTime'], 'shixin_sex'+str(s):val['sex'], 'shixin_age'+str(s):val['age'] 
                        ,'shixin_lxqk'+str(s):val['lxqk'], 'shixin_yjCode'+str(s):val['yjCode'], 'shixin_court'+str(s):val['court']
                        ,'shixin_idcardNo'+str(s): val['idcardNo'], 'shixin_yjdw'+str(s): val['yjdw'], 'shixin_jtqx'+str(s): val['jtqx']
                        ,'shixin_pname'+str(s): val['pname'], 'shixin_province'+str(s): val['province'], 'shixin_caseNo'+str(s): val['caseNo']
                        ,'shixin_postTime'+str(s): val['postTime'], 'shixin_body'+str(s):val['body']})
                    if 'matchRatio' in val.keys():
                        res_dic.update({'shixin_matchRatio'+str(q):val['matchRatio']})
                    s = s + 1
                if val['dataType'] == 'fygg':
                    res_dic.update({'fygg_sortTime'+str(d):val['sortTime'], 'fygg_layout'+str(d): val['layout'], 'fygg_pname'+str(d):val['pname']
                        ,'fygg_court'+str(d): val['court'], 'fygg_ggType'+str(d):val['ggType'], 'fygg_body'+str(d):val['body']})
                    if 'matchRatio' in val.keys():
                        res_dic.update({'fygg_matchRatio'+str(q):val['matchRatio']})
                    d = d + 1
                if val['dataType'] == 'bgt':
                    res_dic.update({'bgt_sortTime'+str(f):val['sortTime'], 'bgt_bgDate'+str(f): val['bgDate'], 'bgt_court'+str(f):val['court']
                        ,'bgt_proposer'+str(f):val['proposer'],'bgt_idcardNo'+str(f):val['idcardNo'],'bgt_caseCause'+str(f):val['caseCause']
                        ,'bgt_unnexeMoney'+str(f): val['unnexeMoney'], 'bgt_address'+str(f):val['address'], 'bgt_pname'+str(f):val['pname']
                        ,'bgt_caseNo'+str(f): val['caseNo'], 'bgt_yiju'+str(f):val['yiju'], 'bgt_execMoney'+str(f):val['execMoney']
                        ,'bgt_body'+str(f):val['body']})
                    if 'matchRatio' in val.keys():
                        res_dic.update({'bgt_matchRatio'+str(q):val['matchRatio']})
                    f = f + 1
        if 'entryList' in data.keys():
            for val in data['entryList']:
                for k in val:
                    if val[k] and type(val[k])==type(u'sadf'):
                        if ';' in val[k]:
                            val.update({k:val[k].replace(';','')})
                if val['dataType'] == 'ktgg':
                    res_dic.update({'ktgg_sortTime'+str(q): val['sortTime'], 'ktgg_plaintiff'+str(q): val['plaintiff'], 'ktgg_organizer'+str(q): val['organizer']
                        ,'ktgg_courtroom'+str(q): val['courtroom'], 'ktgg_court'+str(q): val['court'], 'ktgg_title'+str(q): val['title']
                        ,'ktgg_caseCause'+str(q): val['caseCause'], 'ktgg_judge'+str(q): val['judge'], 'ktgg_caseNo'+str(q): val['caseNo']
                        ,'ktgg_defendant'+str(q): val['defendant'], 'ktgg_body'+str(q): val['body']})
                    if 'matchRatio' in val.keys():
                        res_dic.update({'ktgg_matchRatio'+str(q):val['matchRatio']})
                    q = q +1
                if val['dataType'] == 'ajlc':
                    res_dic.update({'ajlc_sortTime'+str(w):val['sortTime'], 'ajlc_member'+str(w): val['member'], 'ajlc_clerkPhone'+str(w): val['clerkPhone']
                        ,'ajlc_caseType'+str(w): val['caseType'],'ajlc_trialProcedure'+str(w):val['trialProcedure'], 'ajlc_sentencingDate'+str(w):val['sentencingDate']
                        ,'ajlc_status'+str(w): val['status'], 'ajlc_caseStatus'+str(w): val['caseStatus'], 'ajlc_organizer'+str(w): val['organizer']
                        ,'ajlc_filingDate'+str(w): val['filingDate'], 'ajlc_court'+str(w): val['court'], 'ajlc_ajlcStatus'+str(w): val['ajlcStatus']
                        ,'ajlc_chiefJudge'+str(w): val['chiefJudge'], 'ajlc_caseCause'+str(w): val['caseCause'], 'ajlc_trialLimitDate'+str(w): val['trialLimitDate']
                        ,'ajlc_clerk'+str(w): val['clerk'], 'ajlc_judge'+str(w): val['judge'], 'ajlc_actionObject'+str(w): val['actionObject']
                        ,'ajlc_pname'+str(w): val['pname'], 'ajlc_caseNo'+str(w): val['caseNo'], 'ajlc_effectiveDate'+str(w): val['effectiveDate']
                        ,'ajlc_body'+str(w): val['body']})
                    if 'matchRatio' in val.keys():
                        res_dic.update({'ajlc_matchRatio'+str(q):val['matchRatio']})
                    w = w + 1
                if val['dataType'] == 'wdhmd':
                    res_dic.update({'wdhmd_updateTime'+str(e): val['updateTime'], 'wdhmd_sortTime'+str(e): val['sortTime']
                        ,'wdhmd_execCourt'+str(e): val['execCourt'], 'wdhmd_whfx'+str(e): val['whfx'], 'wdhmd_bjbx'+str(e): val['bjbx'], 'wdhmd_caseCode'+str(e): val['caseCode']
                        ,'wdhmd_sourceName'+str(e): val['sourceName'], 'wdhmd_datasource'+str(e): val['datasource'], 'wdhmd_yhje'+str(e):val['yhje'], 'wdhmd_body'+str(e):val['body']})
                    if 'matchRatio' in val.keys():
                        res_dic.update({'wdhmd_matchRatio'+str(q):val['matchRatio']})
                    if 'age' in val.keys():
                        res_dic.update({'wdhmd_age'+str(e):val['age'], 'wdhmd_pname'+str(e): val['pname'], 'wdhmd_sex'+str(e):val['sex'],'wdhmd_phone'+str(e):val['phone']
                            ,'wdhmd_idcardNo'+str(e):val['idcardNo'], 'wdhmd_birthPlace'+str(e): val['birthPlace'], 'wdhmd_address'+str(e): val['address']
                            ,'wdhmd_email'+str(e):val['email'], 'wdhmd_mobile'+str(e): val['mobile']})
                    e = e + 1 
                if val['dataType'] == 'cpws':
                    res_dic.update({'cpws_sortTime'+str(r):val['sortTime'],'cpws_caseType'+str(r):val['caseType'],'cpws_trialProcedure'+str(r):val['trialProcedure']
                        ,'cpws_court'+str(r):val['court'],'cpws_title'+str(r):val['title'],'cpws_judge'+str(r):val['judge']
                        ,'cpws_caseNo'+str(r):val['caseNo'],'cpws_judgeResult'+str(r):val['judgeResult'],'cpws_caseCause'+str(r):val['caseCause']
                        ,'cpws_yiju'+str(r):val['yiju'],'cpws_courtRank'+str(r):val['courtRank'],'cpws_body'+str(r):val['body']
                        })
                    if 'matchRatio' in val.keys():
                        res_dic.update({'cpws_matchRatio'+str(q):val['matchRatio']})
                    r = r + 1
                if val['dataType'] == 'zxgg':
                    res_dic.update({'zxgg_sortTime'+str(a):val['sortTime'], 'zxgg_title'+str(a):val['title'], 'zxgg_pname'+str(a): val['pname']
                        ,'zxgg_court'+str(a):val['court'],'zxgg_proposer'+str(a):val['proposer'],'zxgg_caseNo'+str(a):val['caseNo']
                        ,'zxgg_caseState'+str(a):val['caseState'],'zxgg_idcardNo'+str(a):val['idcardNo'],'zxgg_execMoney'+str(a):val['execMoney']
                        ,'zxgg_body'+str(a):val['body']})
                    a = a + 1
                if val['dataType'] == 'shixin':
                    res_dic.update({'shixin_sortTime'+str(s):val['sortTime'], 'shixin_sex'+str(s):val['sex'], 'shixin_age'+str(s):val['age'] 
                        ,'shixin_lxqk'+str(s):val['lxqk'], 'shixin_yjCode'+str(s):val['yjCode'], 'shixin_court'+str(s):val['court']
                        ,'shixin_idcardNo'+str(s): val['idcardNo'], 'shixin_yjdw'+str(s): val['yjdw'], 'shixin_jtqx'+str(s): val['jtqx']
                        ,'shixin_pname'+str(s): val['pname'], 'shixin_province'+str(s): val['province'], 'shixin_caseNo'+str(s): val['caseNo']
                        ,'shixin_postTime'+str(s): val['postTime'], 'shixin_body'+str(s):val['body']})
                    if 'matchRatio' in val.keys():
                        res_dic.update({'shixin_matchRatio'+str(q):val['matchRatio']})
                    s = s + 1
                if val['dataType'] == 'fygg':
                    res_dic.update({'fygg_sortTime'+str(d):val['sortTime'], 'fygg_layout'+str(d): val['layout'], 'fygg_pname'+str(d):val['pname']
                        ,'fygg_court'+str(d): val['court'], 'fygg_ggType'+str(d):val['ggType'], 'fygg_body'+str(d):val['body']})
                    if 'matchRatio' in val.keys():
                        res_dic.update({'fygg_matchRatio'+str(q):val['matchRatio']})
                    d = d + 1
                if val['dataType'] == 'bgt':
                    res_dic.update({'bgt_sortTime':val['sortTime'], 'bgt_bgDate': val['bgDate'], 'bgt_court':val['court']
                        ,'bgt_proposer':val['proposer'],'bgt_idcardNo':val['idcardNo'],'bgt_caseCause':val['caseCause']
                        ,'bgt_unnexeMoney': val['unnexeMoney'], 'bgt_address':val['address'], 'bgt_pname':val['pname']
                        ,'bgt_caseNo': val['caseNo'], 'bgt_yiju':val['yiju'], 'bgt_execMoney':val['execMoney']
                        ,'bgt_body':val['body']})
                    if 'matchRatio' in val.keys():
                        res_dic.update({'bgt_matchRatio'+str(q):val['matchRatio']})
                    f = f + 1
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info,"interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def hf_bcjq(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'realName': que_line['name'].strip(),
        'idCard':que_line['id'].strip(),
        'bankCard': que_line['bank_card1'].strip(),
        'mobile': que_line['cell'].strip(),
        'client_type': '100002',
        'swift_number': swift_number
    }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        res_dic.update({"costTime": data['costTime']})
        if 'msg' in data.keys():
            res_dic.update({"resCode": data['msg']['code']})
        if 'data' in data.keys():
            resCode = data['data'][0]['record'][0]['resCode']
        if resCode == '00':
            res_dic.update({'resCode': "0000"})
        elif resCode == '06':
            res_dic.update({'resCode': "9941"})
        elif resCode in ['01','02','03','04','05']:
            res_dic.update({'resCode': "1111"})
        elif resCode in ['07','09','12','13','14','15','16','17','18','19','98']:
            res_dic.update({'resCode': "1111"})
        elif resCode == '23':
            res_dic.update({'resCode': "9924"})
        else:
            res_dic.update({'resCode': "9999"})
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def zyhl_ydsj1(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'phone': que_line['cell'].strip(),
        'queryid': '0000000000001',
        'client_type': '100002',
        'swift_number': swift_number
    }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        res_dic.update({"costTime": data['costTime']})
        for obj in data['ServResult']:
            if obj['Name'] == 'OnNetState':
                res_dic.update({'value': obj['AttrList']['Value'], 'isvalid': obj['AttrList']['IsValid']})
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def fy_mbtwo(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'mobile': que_line['cell'].strip(),
        'name': que_line['name'].strip(),
        'client_type': '100002',
        'swift_number': swift_number
    }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        res_dic.update({"costTime":data['costTime'], "msg":data["msg"], "result":data['result']})
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def blxxd(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'param': que_line['name'].strip()+','+que_line['id'].strip(),
        'client_type': '100002',
        'swift_number': swift_number
        }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        
        if isinstance(data, dict):
            res_dic.update({"costTime":data['costTime'], "message_status":data["message"]["status"], "message_value":data['message']["value"]})
            if "#text" in data["badInfoDs"][0]["wybs"]:
                res_dic.update({"wybs": data["badInfoDs"][0]["wybs"]["#text"]})
            else:
                res_dic.update({"wybs": ''})
            if "#text" in data["badInfoDs"][0]["code"]:
                res_dic.update({"status": data["badInfoDs"][0]["code"]["#text"]})
            else:
                res_dic.update({"status": ''})
            if "#text" in data["badInfoDs"][0]["message"]:
                res_dic.update({"value": data["badInfoDs"][0]["message"]["#text"]})
            else:
                res_dic.update({"value": ''})
            if "#text" in data["badInfoDs"][0]["checkCode"]:
                res_dic.update({"checkCode": data["badInfoDs"][0]["checkCode"]["#text"]})
            else:
                res_dic.update({"checkCode": ''})
            if "#text" in data["badInfoDs"][0]["checkMsg"]:
                res_dic.update({"checkMsg": data["badInfoDs"][0]["checkMsg"]["#text"]})
            else:
                res_dic.update({"checkMsg": ''})
            if data["badInfoDs"][0]["item"]:
                if isinstance(data["badInfoDs"][0]["item"], list):
                    num = 1
                    for val in data["badInfoDs"][0]["item"]:
                        if len(val["caseType"]) == 2:
                            res_dic.update({"caseType"+str(num): val["caseType"]["#text"]})
                        else:
                            res_dic.update({"caseType"+str(num): ''})
                        if len(val["caseTime"]) == 2:
                            res_dic.update({"caseTime"+str(num): val["caseTime"]["#text"]})
                        else:
                            res_dic.update({"caseTime"+str(num): ''})
                        if len(val["caseSource"]) == 2:
                            res_dic.update({"caseSource"+str(num): val['caseSource']["#text"]})
                        else:
                            res_dic.update({'caseSource'+str(num): ''})
                        num = num + 1
                if isinstance(data["badInfoDs"][0]["item"], dict):
                    if len(data["badInfoDs"][0]["item"]["caseType"]) == 2:
                        res_dic.update({"caseType1": data["badInfoDs"][0]["item"]["caseType"]["#text"]})
                    else:
                        res_dic.update({"caseType1": ''})
                    if len(data["badInfoDs"][0]["item"]["caseTime"]) == 2:
                        res_dic.update({"caseTime1": data["badInfoDs"][0]["item"]["caseTime"]["#text"]})
                    else:
                        res_dic.update({"caseTime1": ''})
                    if len(data["badInfoDs"][0]["item"]["caseSource"]) == 2:
                        res_dic.update({"caseSource1": data["badInfoDs"][0]["item"]['caseSource']["#text"]})
                    else:
                        res_dic.update({"caseSource1": ""})
                    
        if isinstance(data, list):
            res_dic.update({"message_status":data[0]["status"], "message_value":data[0]["value"]})

        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def qcc_dwtz(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'idNum': que_line['id'].strip(),
        'client_type': '100002',
        'swift_number': swift_number
    }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        data = json.loads(rescls.data)
        # 打平
        res_dic.update({"hncode": '00'})
        res_dic.update({"costTime":data['costTime'], "Api_Status":data["Status"], "Message":data["Message"]})
        if 'Result' in data.keys() and data["Result"]:
            for i in data['Result']:
                if i == 'PunishBreakInfoList' and data['Result'][i]:
                    x = 1
                    for j in data['Result'][i]:
                        for k,v in j.items():
                            res_dic.update({'PB_'+k+str(num):v})
                        x = x + 1
                if i == 'PunishedInfoList' and data['Result'][i]:
                    x = 1
                    for j in data['Result'][i]:
                        for k,v in j.items():
                            res_dic.update({'P_'+k+str(num):v})
                        x = x + 1
                if i == 'RyPosShaInfoList' and data['Result'][i]:
                    x = 1
                    for j in data['Result'][i]:
                        for k,v in j.items():
                            res_dic.update({'RPS_'+k+str(num):v})
                        res_dic.pop('RPS_ConForm'+str(num))
                        res_dic.pop('RPS_FundedRatio'+str(num))
                        x = x + 1
                if i == 'RyPosPerInfoList' and data['Result'][i]:
                    x = 1
                    for j in data['Result'][i]:
                        for k,v in j.items():
                            res_dic.update({'RPP_'+k+str(num):v})
                        x = x + 1
                if i == 'RyPosFrInfoList' and data['Result'][i]:
                    x = 1
                    for j in data['Result'][i]:
                        for k,v in j.items():
                            res_dic.update({'RPF_'+k+str(num):v})
                        x = x + 1
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def sy_sfztwo(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'idCard': que_line['id'].strip(),
        'name': que_line['name'].strip(),
        'client_type': '100002',
        'swift_number': swift_number
    }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        res_dic.update({"costTime":data['costTime'], "msg":data["msg"]})
        if 'result' in data.keys() and data["result"]:
            res_dic.update({"result": data['result']['result'], "gender": data['result']['gender']})
            if data['result']['result'] == "1":
                res_dic.update({"birthday": data['result']['birthday'], "photo_base64": data['result']['photo_base64']})
                if "region" in data['result'].keys():
                    res_dic.update({"region": data['result']['region']})
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def rjh_ltsz(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'mobile': que_line['cell'].strip(),
        'client_type': '100002',
        'swift_number': swift_number
        }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        res_dic.update({"costTime":data['costTime']})
        if "code" in data.keys():
            res_dic.update({"code":data['code']})
        if "message" in data.keys():
            res_dic.update({"message":data["message"]})
        if 'data' in data.keys() and data['data']:
            res_dic.update({"c_cc": data['data']['last_1']['c']['c_cc'],
                            "c_db": data['data']['last_1']['c']['c_db'],
                            "c_dc": data['data']['last_1']['c']['c_dc'],
                            "c_ctc": data['data']['last_1']['c']['c_ctc'],
                            "c_dbn": data['data']['last_1']['c']['c_dbn'],
                            "c_cbn": data['data']['last_1']['c']['c_cbn']
                            })
            for key1 in data['data']:
                if key1 == 'last_1':
                    if 'p' in data['data']['last_1'].keys():
                        for key2,val in data['data']['last_1']['p'].items():
                            res_dic.update({'last1_'+key2: val})
                    if 'c' in data['data']['last_1'].keys():
                        for key2,val in data['data']['last_1']['c'].items():
                            res_dic.update({'last1_'+key2: val})
                    if 'i' in data['data']['last_1'].keys():
                        for key2,val in data['data']['last_1']['i'].items():
                            res_dic.update({'last1_'+key2: val})
                    if 'o' in data['data']['last_1'].keys():
                        for key2,val in data['data']['last_1']['o'].items():
                            res_dic.update({'last1_'+key2: val})
                if key1 == 'last_3':
                    if 'p' in data['data']['last_3'].keys():
                        for key2,val in data['data']['last_3']['p'].items():
                            res_dic.update({'last3_'+key2: val})
                    if 'c' in data['data']['last_3'].keys():
                        for key2,val in data['data']['last_3']['c'].items():
                            res_dic.update({'last3_'+key2: val})
                    if 'i' in data['data']['last_3'].keys():
                        for key2,val in data['data']['last_3']['i'].items():
                            res_dic.update({'last3_'+key2: val})
                    if 'o' in data['data']['last_3'].keys():
                        for key2,val in data['data']['last_3']['o'].items():
                            res_dic.update({'last3_'+key2: val})
                if key1 == 'last_6':
                    if 'p' in data['data']['last_6'].keys():
                        for key2,val in data['data']['last_6']['p'].items():
                            res_dic.update({'last6_'+key2: val})
                    if 'c' in data['data']['last_6'].keys():
                        for key2,val in data['data']['last_6']['c'].items():
                            res_dic.update({'last6_'+key2: val})
                    if 'i' in data['data']['last_6'].keys():
                        for key2,val in data['data']['last_6']['i'].items():
                            res_dic.update({'last6_'+key2: val})
                    if 'o' in data['data']['last_6'].keys():
                        for key2,val in data['data']['last_6']['o'].items():
                            res_dic.update({'last6_'+key2: val})
                if key1 == 'last_12':
                    if 'p' in data['data']['last_12'].keys():
                        for key2,val in data['data']['last_12']['p'].items():
                            res_dic.update({'last12_'+key2: val})
                    if 'c' in data['data']['last_12'].keys():
                        for key2,val in data['data']['last_12']['c'].items():
                            res_dic.update({'last12_'+key2: val})
                    if 'i' in data['data']['last_12'].keys():
                        for key2,val in data['data']['last_12']['i'].items():
                            res_dic.update({'last12_'+key2: val})
                    if 'o' in data['data']['last_12'].keys():
                        for key2,val in data['data']['last_12']['o'].items():
                            res_dic.update({'last12_'+key2: val})
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def hjxxcx(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'identity_code': que_line['id'].strip(),
        'identity_name': que_line['name'].strip(),
        'client_type': '100002',
        'swift_number': swift_number
    }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        res_dic.update({"costTime":data['costTime'], "code":data["api_status"]["code"]
                , "description":data["api_status"]["description"], "api_status":data["api_status"]["status"]})
        if 'data' in data.keys():
            res_dic.update({"status":data["data"]["status"], 'result':data["data"]["result"]})
            if 'output' in data['data'].keys():
                res_dic.update({"address": data['data']['output']['address']
                    , "birthPlace": data['data']['output']['birthPlace'], "birthday": data['data']['output']['birthday']
                    , "company": data['data']['output']['company'], "edu": data['data']['output']['edu']
                    , "formerName": data['data']['output']['formerName'], "maritalStatus": data['data']['output']['maritalStatus']
                    , "nation": data['data']['output']['nation'], "originPlace": data['data']['output']['originPlace']
                    , "sex": data['data']['output']['sex']})
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def xb_shsb(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'identity_code': que_line['id'].strip(),
        'identity_name': que_line['name'].strip(),
        'client_type': '100002',
        'swift_number': swift_number
    }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        res_dic.update({"costTime":data['costTime'], "code":data["api_status"]["code"]
                , "description":data["api_status"]["description"]
                , "api_status":data["api_status"]["status"], })
        if 'data' in data.keys():
            res_dic.update({"result":data['data']['result'], 'status': data['data']['status']})
            if 'output' in data['data'].keys():
                num = 1
                for every in data["data"]["output"]:
                    res_dic.update({"companyName"+str(num): every["companyName"]
                        , "depositStatus"+str(num): every["depositStatus"]
                        , "updateTime"+str(num): every["updateTime"]})    
                    num = num + 1
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def zhx_hvvkjzpf(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'codes': [{"key":"zhx_hlxw","code":que_line['id'].strip()}],
        'client_type': '100002',
        'swift_number': swift_number
        }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        res_dic.update({"costTime":data['costTime'], "result":data['result']})
        if 'datas' in data.keys():
            if isinstance(data['datas'], dict):
                if 'score' in data['datas'].keys():
                    res_dic.update({'score': data['datas']['score']})
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def ylzc_zfxfxwph(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'param': que_line['bank_card1'],
        'yearmonth': ''.join(que_line['user_date'].split('-'))[0:6],
        'client_type': '100002',
        'swift_number': swift_number
        }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        res_dic.update({"costTime":data['costTime'], "error_code":data['error_code']})
        if 'data' in data.keys():
            if isinstance(data['data'], list):
                if data['data'][0]:
                    for key in data['data'][0].keys():
                        if data['data'][0][key] == "\"null\"":
                            res_dic.update({key: ""})
                        else:
                            res_dic.update({key: data['data'][0][key]})
        if 'account_no' in res_dic.keys():
            res_dic.pop('account_no')
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def qcc_qydwtz(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'keyword':que_line['biz_name'],
        'pageSize': '10',
        'pageIndex': '1',
        'client_type': '100002',
        'swift_number': swift_number
        }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        if 'costTime' in data.keys():
            res_dic.update({"Status":data['Status'],"costTime":data['costTime']})
        if 'Result' in data.keys(): 
            if data['Result']:
                length = len(data['Result'])
                max_range = range(1,length+1)
                items = zip(max_range, data['Result'])
                for item in items:
                    x = str(item[0])
                    for key in item[1]:
                        new_key = key+x
                        res_dic.update({new_key: item[1][key]})
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def zskj_bcjq(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'name': que_line['name'].strip(),
        'idCard': que_line['id'].strip(),
        'accountNo': que_line['bank_card1'].strip(),
        'mobile': que_line['cell'].strip(),
        'client_type': '100002',
        'swift_number': swift_number
        }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        res_dic.update({"costTime":data['costTime'], "msg":data['MESSAGE'], 'result':data['RESULT']})
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def fy_ydcmc1(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'mobile': que_line['cell'].strip(),
        'client_type': '100002',
        'swift_number': swift_number
        }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        for key, value in data.items():
            if isinstance(value, dict):
                for result in value.keys():
                    res_dic.update({result: value[result]})
            else:
                res_dic.update({key: value})

        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def blxxb(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'param': que_line['name'].strip() + ',' + que_line['id'].strip(),
        'client_type': '100002',
        'swift_number': swift_number
        }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        if isinstance(data, dict):
            if 'costTime' in data.keys():
                res_dic.update({'costTime': data['costTime']})
            elif 'costTime' in data.keys():
                res_dic.update({'costTime': data['costTime']})
            if 'message' in data.keys() and data['message']:
                res_dic.update({'message_status': data['message']['status'], 'message_value': data['message']['value']})
            if 'priskChecks' in data.keys() and data['priskChecks']:
                for one in data['priskChecks']:
                    if isinstance(one, dict):
                        res_dic.update({'name1': one.get('@inputXm', ''), 'id1': one.get('@inputZjhm', '')})
                        if 'message' in one.keys():
                            res_dic.update({'status': one['message'].get('status', ''), 'value': one['message'].get('value', '')})
                        for key in ['wybs', 'checkCode', 'checkMsg']:
                            if key  in one.keys():
                                res_dic.update({key: one[key].get('#text', '')})
                        if 'caseDetail' in one.keys() and one['caseDetail']:
                            if isinstance(one['caseDetail'], list):
                                num = 0
                                for every in one['caseDetail']:
                                    num = num + 1 
                                    res_dic.update({'caseType'+str(num): every['caseType'].get('#text', ''), 'caseSource'+str(num): every['caseSource'].get('#text', ''), 'caseTime'+str(num): every['caseTime'].get('#text', '')})
                            if isinstance(one['caseDetail'], dict):
                                res_dic.update({'caseType1': one['caseDetail']['caseType'].get('#text', ''), 'caseSource1': one['caseDetail']['caseSource'].get('#text', ''), 'caseTime1': one['caseDetail']['caseTime'].get('#text', '')})
        else:
            if isinstance(data[0], dict):
                for key, value in data[0].items():
                    res_dic.update({key: value})
        
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def szdj(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {
        'mobileid': que_line['cell'].strip(),
        'querymonth': ''.join(que_line['user_date'].split('-'))[0:6],
        'client_type': '100002',
        'swift_number': swift_number
        }
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00',"costTime": data['costTime']})
        retcode = data['retcode']
        if retcode != '0000':
            res_dic.update({'flag_accountChangeMonth': '0'})
        else:
            res_dic.update({"flag_accountChangeMonth":'1'})
            if 'br_v2_1_mobile_6m' in data.keys():
                for data_6m in data['br_v2_1_mobile_6m']:
                    if data_6m["@id"] == "1":
                        text = data_6m["#text"].split(',')
                        res_dic.update({"ac_m1_debit_balance":text[0],"ac_m1_debit_out":text[1],"ac_m1_debit_out_num":text[2],"ac_m1_debit_invest":text[3],
                            "ac_m1_debit_repay":text[4],"ac_m1_debit_in":text[5],"ac_m1_debit_in_num":text[6],"ac_m1_credit_out":text[7],
                            "ac_m1_credit_out_num":text[8],"ac_m1_credit_cash":text[9],"ac_m1_credit_in":text[10],"ac_m1_credit_in_num":text[11],
                            "ac_m1_credit_def":text[12],"ac_m1_loan":text[13],"ac_m1_credit_status":text[14],"ac_m1_cons":text[15],"ac_m1_max_in":text[16]})
                    
                    if data_6m["@id"] == "2":
                        text = data_6m["#text"].split(',')
                        res_dic.update({"ac_m2_debit_balance":text[0],"ac_m2_debit_out":text[1],"ac_m2_debit_out_num":text[2],"ac_m2_debit_invest":text[3],
                            "ac_m2_debit_repay":text[4],"ac_m2_debit_in":text[5],"ac_m2_debit_in_num":text[6],"ac_m2_credit_out":text[7],
                            "ac_m2_credit_out_num":text[8],"ac_m2_credit_cash":text[9],"ac_m2_credit_in":text[10],"ac_m2_credit_in_num":text[11],
                            "ac_m2_credit_def":text[12],"ac_m2_loan":text[13],"ac_m2_credit_status":text[14],"ac_m2_cons":text[15],"ac_m2_max_in":text[16]})

                    if data_6m["@id"] == "3":
                        text = data_6m["#text"].split(',')
                        res_dic.update({"ac_m3_debit_balance":text[0],"ac_m3_debit_out":text[1],"ac_m3_debit_out_num":text[2],"ac_m3_debit_invest":text[3],
                            "ac_m3_debit_repay":text[4],"ac_m3_debit_in":text[5],"ac_m3_debit_in_num":text[6],"ac_m3_credit_out":text[7],
                            "ac_m3_credit_out_num":text[8],"ac_m3_credit_cash":text[9],"ac_m3_credit_in":text[10],"ac_m3_credit_in_num":text[11],
                            "ac_m3_credit_def":text[12],"ac_m3_loan":text[13],"ac_m3_credit_status":text[14],"ac_m3_cons":text[15],"ac_m3_max_in":text[16]})

                    if data_6m["@id"] == "4":
                        text = data_6m["#text"].split(',')
                        res_dic.update({"ac_m4_debit_balance":text[0],"ac_m4_debit_out":text[1],"ac_m4_debit_out_num":text[2],"ac_m4_debit_invest":text[3],
                            "ac_m4_debit_repay":text[4],"ac_m4_debit_in":text[5],"ac_m4_debit_in_num":text[6],"ac_m4_credit_out":text[7],
                            "ac_m4_credit_out_num":text[8],"ac_m4_credit_cash":text[9],"ac_m4_credit_in":text[10],"ac_m4_credit_in_num":text[11],
                            "ac_m4_credit_def":text[12],"ac_m4_loan":text[13],"ac_m4_credit_status":text[14],"ac_m4_cons":text[15],"ac_m4_max_in":text[16]})

                    if data_6m["@id"] == "5":
                        text = data_6m["#text"].split(',')
                        res_dic.update({"ac_m5_debit_balance":text[0],"ac_m5_debit_out":text[1],"ac_m5_debit_out_num":text[2],"ac_m5_debit_invest":text[3],
                            "ac_m5_debit_repay":text[4],"ac_m5_debit_in":text[5],"ac_m5_debit_in_num":text[6],"ac_m5_credit_out":text[7],
                            "ac_m5_credit_out_num":text[8],"ac_m5_credit_cash":text[9],"ac_m5_credit_in":text[10],"ac_m5_credit_in_num":text[11],
                            "ac_m5_credit_def":text[12],"ac_m5_loan":text[13],"ac_m5_credit_status":text[14],"ac_m5_cons":text[15],"ac_m5_max_in":text[16]})

                    if data_6m["@id"] == "6":
                        text = data_6m["#text"].split(',')
                        res_dic.update({"ac_m6_debit_balance":text[0],"ac_m6_debit_out":text[1],"ac_m6_debit_out_num":text[2],"ac_m6_debit_invest":text[3],
                            "ac_m6_debit_repay":text[4],"ac_m6_debit_in":text[5],"ac_m6_debit_in_num":text[6],"ac_m6_credit_out":text[7],
                            "ac_m6_credit_out_num":text[8],"ac_m6_credit_cash":text[9],"ac_m6_credit_in":text[10],"ac_m6_credit_in_num":text[11],
                            "ac_m6_credit_def":text[12],"ac_m6_loan":text[13],"ac_m6_credit_status":text[14],"ac_m6_cons":text[15],"ac_m6_max_in":text[16]})


            if 'br_v2_1_mobile_18m' in data.keys():
                for data_6m in data['br_v2_1_mobile_18m']:
                    if data_6m["@id"] == "1":
                        text = data_6m["#text"].split(',')
                        res_dic.update({"ac_m1m3_debit_balance":text[0],"ac_m1m3_debit_out":text[1],"ac_m1m3_debit_out_num":text[2],"ac_m1m3_debit_invest":text[3],
                            "ac_m1m3_debit_repay":text[4],"ac_m1m3_debit_in":text[5],"ac_m1m3_debit_in_num":text[6],"ac_m1m3_credit_out":text[7],
                            "ac_m1m3_credit_out_num":text[8],"ac_m1m3_credit_cash":text[9],"ac_m1m3_credit_in":text[10],"ac_m1m3_credit_in_num":text[11],
                            "ac_m1m3_credit_def":text[12],"ac_m1m3_loan":text[13],"ac_m1m3_credit_status":text[14],"ac_m1m3_cons":text[15],"ac_m1m3_max_in":text[16]})
                    if data_6m["@id"] == "4":
                        text = data_6m["#text"].split(',')
                        res_dic.update({"ac_m4m6_debit_balance":text[0],"ac_m4m6_debit_out":text[1],"ac_m4m6_debit_out_num":text[2],"ac_m4m6_debit_invest":text[3],
                            "ac_m4m6_debit_repay":text[4],"ac_m4m6_debit_in":text[5],"ac_m4m6_debit_in_num":text[6],"ac_m4m6_credit_out":text[7],
                            "ac_m4m6_credit_out_num":text[8],"ac_m4m6_credit_cash":text[9],"ac_m4m6_credit_in":text[10],"ac_m4m6_credit_in_num":text[11],
                            "ac_m4m6_credit_def":text[12],"ac_m4m6_loan":text[13],"ac_m4m6_credit_status":text[14],"ac_m4m6_cons":text[15],"ac_m4m6_max_in":text[16]})
                    if data_6m["@id"] == "7":
                        text = data_6m["#text"].split(',')
                        res_dic.update({"ac_m7m9_debit_balance":text[0],"ac_m7m9_debit_out":text[1],"ac_m7m9_debit_out_num":text[2],"ac_m7m9_debit_invest":text[3],
                            "ac_m7m9_debit_repay":text[4],"ac_m7m9_debit_in":text[5],"ac_m7m9_debit_in_num":text[6],"ac_m7m9_credit_out":text[7],
                            "ac_m7m9_credit_out_num":text[8],"ac_m7m9_credit_cash":text[9],"ac_m7m9_credit_in":text[10],"ac_m7m9_credit_in_num":text[11],
                            "ac_m7m9_credit_def":text[12],"ac_m7m9_loan":text[13],"ac_m7m9_credit_status":text[14],"ac_m7m9_cons":text[15],"ac_m7m9_max_in":text[16]})
                    if data_6m["@id"] == "10":
                        text = data_6m["#text"].split(',')
                        res_dic.update({"ac_m10m12_debit_balance":text[0],"ac_m10m12_debit_out":text[1],"ac_m10m12_debit_out_num":text[2],"ac_m10m12_debit_invest":text[3],
                            "ac_m10m12_debit_repay":text[4],"ac_m10m12_debit_in":text[5],"ac_m10m12_debit_in_num":text[6],"ac_m10m12_credit_out":text[7],
                            "ac_m10m12_credit_out_num":text[8],"ac_m10m12_credit_cash":text[9],"ac_m10m12_credit_in":text[10],"ac_m10m12_credit_in_num":text[11],
                            "ac_m10m12_credit_def":text[12],"ac_m10m12_loan":text[13],"ac_m10m12_credit_status":text[14],"ac_m10m12_cons":text[15],"ac_m10m12_max_in":text[16]})
                    if data_6m["@id"] == "13":
                        text = data_6m["#text"].split(',')
                        res_dic.update({"ac_m13m15_debit_balance":text[0],"ac_m13m15_debit_out":text[1],"ac_m13m15_debit_out_num":text[2],"ac_m13m15_debit_invest":text[3],
                            "ac_m13m15_debit_repay":text[4],"ac_m13m15_debit_in":text[5],"ac_m13m15_debit_in_num":text[6],"ac_m13m15_credit_out":text[7],
                            "ac_m13m15_credit_out_num":text[8],"ac_m13m15_credit_cash":text[9],"ac_m13m15_credit_in":text[10],"ac_m13m15_credit_in_num":text[11],
                            "ac_m13m15_credit_def":text[12],"ac_m13m15_loan":text[13],"ac_m13m15_credit_status":text[14],"ac_m13m15_cons":text[15],"ac_m13m15_max_in":text[16]})
                    if data_6m["@id"] == "16":
                        text = data_6m["#text"].split(',')
                        res_dic.update({"ac_m16m18_debit_balance":text[0],"ac_m16m18_debit_out":text[1],"ac_m16m18_debit_out_num":text[2],"ac_m16m18_debit_invest":text[3],
                            "ac_m16m18_debit_repay":text[4],"ac_m16m18_debit_in":text[5],"ac_m16m18_debit_in_num":text[6],"ac_m16m18_credit_out":text[7],
                            "ac_m16m18_credit_out_num":text[8],"ac_m16m18_credit_cash":text[9],"ac_m16m18_credit_in":text[10],"ac_m16m18_credit_in_num":text[11],
                            "ac_m16m18_credit_def":text[12],"ac_m16m18_loan":text[13],"ac_m16m18_credit_status":text[14],"ac_m16m18_cons":text[15],"ac_m16m18_max_in":text[16]})

            if "br_mobile_once" in data.keys():
                once = data['br_mobile_once'][0].split(',')
                res_dic.update({'bank_pf_ind':once[0][0],'bank_js_ind':once[0][1],'bank_zs_ind':once[0][2],'bank_zg_ind':once[0][3],'bank_gs_ind':once[0][4],
                    'bank_xy_ind':once[0][5],'bank_pa_ind':once[0][6],'bank_zsx_ind':once[0][7],'bank_jt_ind':once[0][8],'ac_regionno':once[1],'card_index':once[2]})        
            if 'br_mobile_auth' in data.keys():
                auth = data["br_mobile_auth"][0].split(',')
                res_dic.update({'hf_acc_date':auth[0], 'hf_auth_date':auth[1], 'hf_bal_sign':auth[2], 'hf_balance':auth[3], 'hf_user_status':auth[4]})

        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def zcx_sxzx(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})

    if int(que_line['other_var5']) == 2:
        info = {'name': que_line['biz_name'].strip(),
                'type': 2,
                'reqTid': swift_number,
                'client_type': '100002',
                'swift_number': swift_number}
    else:
        info = {'name': que_line['name'].strip(),
                'cid': que_line['id'].strip(),
                'type': 1,
                'reqTid': swift_number,
                'client_type': '100002',
                'swift_number': swift_number}

    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        if isinstance(data, dict):
            resCode = data["resCode"]
            if resCode == '0000' :
                res_dic.update({"resCode":data["resCode"],"resMsg":data["resMsg"],"totalNum":data["totalNum"],"costTime":data["costTime"]})
                if data["data"]:  
                    i = 1
                    for line in data["data"]:
                        for x  in line["entity"]:
                            if line["entity"][x]:
                                res_dic.update({x+str(i):line["entity"][x]})
                            else:
                                res_dic.update({x+str(i):''})
                        i = i + 1
            elif resCode == "2001":
                res_dic.update({"resCode":data["resCode"],"resMsg":data["resMsg"],"totalNum":data["totalNum"],"data":data["data"],"costTime":data["costTime"]})
            elif  resCode == '1001' or resCode == '1002' or resCode == '1003' or resCode == '1013' or resCode == '9999' or resCode == '1011':
                res_dic.update({"resCode":data["resCode"]})
            else:
                res_dic.update({"resCode":data["resCode"],"resMsg":data["resMsg"],"totalNum":data["totalNum"],"data":data["data"],"costTime":data["costTime"]})
 
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def clwz(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {'carnumber': que_line['vehicle_id'].strip(),
            'carcode': que_line['car_code'].strip(),
            'cardrivenumber': que_line['driver_number'].strip(),
            'client_type': '100002',
            'swift_number': swift_number}
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00', "costTime": data['costTime']})
        head = ['Time','Location','Reason','count','status','department','Degree','Code','Archive','Telephone','Excutelocation','Excutedepartment','Category','Latefine','Punishmentaccording','Illegalentry','Locationid','LocationName','DataSourceID','RecordType','Poundage','CanProcess','SecondaryUniqueCode','UniqueCode','DegreePoundage','CanprocessMsg','Other']
        for key in ['ErrorCode', 'Other', 'Success', 'orderNo', 'ErrMessage', 'LastSearchTime']:
            if key in data.keys():
                res_dic.update({key: data[key]})
        if 'Records' in data.keys():
            i = 0
            for one in data['Records']:
                i += 1
                for key in one.keys():
                    if key in head:
                        res_dic.update({key + str(i): one[key]})
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def qyjb(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    info = {'entName': que_line['biz_name'].strip(),
            'client_type': '100002',
            'swift_number': swift_number}
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        head = ['resCode','resMsg','orderNo','entName','frName','regNo','regCap','regCapCur','esDate','opFrom','opTo','entType','entStatus','canDate','revDate','dom','abuItem','cbuItem','opScope','opScoAndForm','regOrg','anCheYear','anCheDate','industryPhyCode','orgNo','administrativeDivisionCode','phone','postalCode','staffNum','authorityName','authorityCode','orgNoStartDate','orgNoEndDate','result','industryCoCode','message']
        for key in ('resCode', 'resMsg', 'orderNo', 'message'):
            if key in data.keys():
                res_dic.update({key: data[key]})
        if 'data' in data.keys() and data['data']:
            for key ,value in data['data'].items():
                if key in head:
                    res_dic.update({key: value})
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def dd(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})
    if 'id' in que_line.keys():
        id_num = que_line['id']
    else:
        id_num = ''
    if 'bank_card1' in que_line.keys():
        cardId = que_line['bank_card1']
    else:
        id_num = ''
    if 'name' in que_line.keys():
        name = que_line['name']
    else:
        name = ''
    info = {'idnumber': id_num,
            'name': name,
            'credit': cardId,
            'tel': que_line['cell'].strip(),
            'fields': que_line['other_var5'].strip().replace('|', ','),
            'client_type': '100002',
            'swift_number': swift_number}
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00'})
        if 'costTime' in data.keys():
            res_dic.update({'costTime': data['costTime']})
        if 'result' in data.keys():
            res_dic.update({'result': data['result']})
        if 'data' in data.keys():
            if isinstance(data['data'], dict):
                for key, item in data['data'].items():
                    item = str(item)
                    res_dic.update({key: item.replace(',', '|').replace('，', '|').replace(';', '|')})
        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


def shbc(line, modal, iceobj, username, cus_username):
    que_line = json.loads(line)
    num = int(que_line['cus_num']) - 1
    swift_number = username + "_" + time.strftime('%Y%m%d%H%M%S') + "_" + str(random.randint(1000, 9999))
    que_line.update({"swift_number": swift_number})
    que_line.update({"cus_username": cus_username})

    info = {'cardId': que_line['bank_card1'].strip(),
            'client_type': '100002',
            'swift_number': swift_number}
    rescls = iceobj.get_data(info, modal)
    res_dic = {}
    status = rescls.status
    
    if status == '0':
        # 打平
        data = json.loads(rescls.data)
        res_dic.update({"hncode": '00','costTime': data['costTime']})
        if "user_date" in que_line.keys():
            date = que_line['user_date'].split('-')
            mon = date[1]
            year = date[0]
            if int(mon) > 1:
                mon = mon - 2
                if mon < 10:
                    mon = '0' + str(mon)
                else:
                    mon = str(mon)
                yearmonth = year + mon
            else:
                year = str(int(year) - 1)
                if int(mon) == 1:
                    mon = str(12)
                else:
                    mon = str(11)
                yearmonth = year + mon

        else:
            year = str(datetime.datetime.now().year)
            mon = str(datetime.datetime.now().month)
            if int(mon) > 1:
                mon = mon - 2
                if mon < 10:
                    mon = '0' + str(mon)
                else:
                    mon = str(mon)
                yearmonth = year + mon
            else:
                year = str(int(year) - 1)
                if int(mon) == 1:
                    mon = str(12)
                else:
                    mon = str(11)
                yearmonth = year + mon
        now = yearmonth
        ran = ['201401','201402','201403','201404','201405','201406','201407','201408','201409','201410'
            ,'201411','201412','201501','201502','201503','201504','201505','201506','201507','201508','201509'
            ,'201510','201511','201512','201601','201602','201603','201604','201605','201606','201607','201608'
            ,'201609','201610','201611','201612','201701','201702','201703','201704','201705','201706','201707'
            ,'201708','201709','201710','201711','201712']
        date_18_mon = ran[:ran.index(now)+1][-18:]
        date_18_mon.sort(reverse = True)
        i = 1
        for key in date_18_mon:
            if key in data['PayConsumption'].keys():
                res_dic.update({
                        "pc_thm"+str(i)+"_pay":data['PayConsumption'][key]['pay'],
                        "pc_thm"+str(i)+"_num":data['PayConsumption'][key]['number'],
                        "pc_thm"+str(i)+"_"+str(i)+"st_pay_mcc":data['PayConsumption'][key]['first_pay_mcc'],
                        "pc_thm"+str(i)+"_"+str(i)+"st_num_mcc":data['PayConsumption'][key]['first_number_mcc'],
                        "pc_thm"+str(i)+"_"+str(i)+"st_pay_mcc":data['PayConsumption'][key]['first_pay_mcc'],
                        "pc_thm"+str(i)+"_"+str(i)+"st_num_mcc":data['PayConsumption'][key]['first_number_mcc'],
                        "pc_thm"+str(i)+"_"+str(i)+"nd_pay_mcc":data['PayConsumption'][key]['second_pay_mcc'],
                        "pc_thm"+str(i)+"_"+str(i)+"nd_num_mcc":data['PayConsumption'][key]['second_number_mcc'],
                        "pc_thm"+str(i)+"_"+str(i)+"rd_pay_mcc":data['PayConsumption'][key]['third_pay_mcc'],
                        "pc_thm"+str(i)+"_"+str(i)+"rd_num_mcc":data['PayConsumption'][key]['third_number_mcc'],
                        "pc_thm"+str(i)+"_max_num_pvn":data['PayConsumption'][key]['max_number_city'],
                        "pc_thm"+str(i)+"_night_pay":data['PayConsumption'][key]['night_pay'],
                        "pc_thm"+str(i)+"_night_num":data['PayConsumption'][key]['night_number'],
                    })
            i = i + 1

        txt_dic = {"res": data}
    else:
        res_dic.update({'hncode': rescls.code})
        txt_dic = {"res": {}}
    deal(que_line)
    res_dic.update(que_line)
    txt_dic.update({"info":info, "interface":','.join(modal)})
    return {"res_dic": res_dic, "data_txt": txt_dic, "num": num}


switch = {
    "hf_bankthree": hf_bankthree,
    "xb_xlxxcx": xb_xlxxcx,
    "zskj_idjy": zskj_idjy,
    "fh_perspre": fh_perspre,
    "fh_comppre": fh_perspre,
    "hf_bcjq": hf_bcjq,
    "zyhl_ydsj1": zyhl_ydsj1,
    "fy_mbtwo": fy_mbtwo,
    "blxxd": blxxd,
    "qcc_dwtz": qcc_dwtz,
    "sy_sfztwo": sy_sfztwo,
    "rjh_ltsz": rjh_ltsz,
    "hjxxcx": hjxxcx,
    "xb_shsb": xb_shsb,
    "zhx_hvvkjzpf": zhx_hvvkjzpf,
    "zhx_hvgcfxbq": zhx_hvvkjzpf,
    "ylzc_zfxfxwph": ylzc_zfxfxwph,
    "qcc_qydwtz": qcc_qydwtz,
    "zskj_bcjq": zskj_bcjq,
    "fy_ydcmc1": fy_ydcmc1,
    "blxxb": blxxb,
    "szdj": szdj,
    "zcx_sxzx": zcx_sxzx,
    "clwz": clwz,
    "qyjb": qyjb,
    "dd": dd,
    "shbc": shbc,
}
