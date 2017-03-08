# -*- coding: utf-8 -*-
import random
import time
import os
import re
import string
import smtplib
import logging

from django.shortcuts import redirect, get_object_or_404
from django.http import StreamingHttpResponse, Http404, JsonResponse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import EmailMessage

from analyst.models import MappingedFile, ReportFile
from customer.models import SourceFile
from account.models import Extra, Member


logger = logging.getLogger('DTS')

Filter = []   # 白名单列表


@login_required
def index(request):
    if not request.user.is_authenticated():
        return redirect('/accounts/login')
    role = request.user.member.role
    if role == 2:
        return redirect('/analyst/filelist/')
    elif role == 1:
        return redirect('/customer/filelist/')
    elif role == 0:
        return redirect('/checker/filelist/')


def send_mail(receiver, subject, content, filepath=None):
    for i in xrange(5):
        try:
            msg = EmailMessage(subject, content, 'dts@100credit.com', receiver)
            msg.content_subtype = "html"
            if filepath:
                msg.attach_file(filepath)
            msg.send()
            break
        except smtplib.SMTPRecipientsRefused:
            user = User.objects.get(email=receiver[0])
            content = user.first_name + ":" + user.email + "邮箱有误，请修改."
            msg = EmailMessage(
                "DTS用户邮箱错误", content, 'dts@100credit.com',
                ['lei.zhang1@100credit.com', 'dts@100credit.com']
            )
            msg.content_subtype = "html"
            msg.send()
            break
        except Exception:
            time.sleep(0.2)


@login_required
def docs(request, *args, **kwargs):

    if re.match(r'^/down/analyst/mapfile/(?P<pk>[0-9]+)/$', request.path):
        mapfile = get_object_or_404(MappingedFile, pk=kwargs['pk'])
        if request.user.member != mapfile.member:
            raise Http404
        basedir = mapfile.file.path

    elif re.match(r'^/down/checker/sourcefile/(?P<pk>[0-9]+)/$', request.path):
        sourcefile = get_object_or_404(SourceFile, pk=kwargs['pk'])
        if request.user.member != sourcefile.custom.analyst.checker:
            raise Http404
        basedir = sourcefile.filename.path

    elif re.match(r'^/down/checker/mapfile/(?P<pk>[0-9]+)/$', request.path):
        mapfile = get_object_or_404(MappingedFile, pk=kwargs['pk'])
        if request.user.member != mapfile.member.checker:
            raise Http404
        basedir = mapfile.file.path

    elif re.match(r'^/down/customer/reportfile/(?P<pk>[0-9]+)/$', request.path):
        reportfile = get_object_or_404(ReportFile, pk=kwargs['pk'])
        if request.user.member != reportfile.source_file.custom:
            raise Http404
        basedir = reportfile.report_file.path

    elif re.match(r'^/docs/$', request.path):
        if request.user.member.role not in [1, 0]:
            raise Http404
        basedir = os.getcwd() + '/static/doc/百融数据测试模板.xlsx'

    _, name = os.path.split(basedir)

    def file_iterator(chunk_size=512):
        with open(basedir) as f:
            while True:
                c = f.read(chunk_size)
                if c:
                    yield c
                else:
                    break

    response = StreamingHttpResponse(file_iterator())
    response['Content-Type'] = 'application/octet-stream'
    response['Content-Disposition'] = 'attachment;filename="{0}"'.format(name)
    return response


@login_required
def delete(request):
    fileid = request.GET.get('fileid')
    if re.match(r'^/delete/reportfile/$', request.path):
        file = get_object_or_404(ReportFile, pk=int(fileid))
        if request.user.member != file.customer:
            raise Http404
        file.delete()

    if re.match(r'^/delete/sourcefile/$', request.path):
        file = get_object_or_404(SourceFile, pk=int(fileid))
        if request.user.member != file.custom.analyst.checker:
            raise Http404
        file.delete()
    return JsonResponse({'msg': 0})


@csrf_exempt
def crm_cre_user(request):
    if request.method != 'POST':
        raise Http404
    cus_username = request.POST.get('cus_username')    #客户账号
    
    first_name = request.POST.get('first_name')
    email = request.POST.get('email')
    city = request.POST.get('city')
    ips = request.POST.get('ips')
    level = request.POST.get('level')

    ana_username = request.POST.get('ana_username')
    if not re.match("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$", email):
        return JsonResponse({'msg': '邮箱格式有误'})

    obj = Extra.objects.all().last()
    obj.ips = obj.ips + ',' + ips
    obj.save()

    try:
        ana_user = User.objects.get(username=ana_username)       
    except User.DoesNotExist:
        return JsonResponse({'msg': '没有该分析师账号'})

    if ana_user.member.role != 2:
        return JsonResponse({'msg': '该商务在DTS系统中的角色不是分析师'})

    password = ''.join([random.choice(string.ascii_letters+string.digits) for _ in range(8)])

    try:
        cus_user = User.objects.get(username=cus_username)
        cus_user.member.analyst = ana_user.member
        cus_user.email = email
        cus_user.first_name = first_name
        cus_user.member.city = city
        cus_user.member.level = level
        cus_user.member.allow_ips = cus_user.member.allow_ips + ',' + ips
        cus_user.member.save()
        cus_user.set_password(password)
        cus_user.save()
    except User.DoesNotExist:
        cus_user = User.objects.create_user(username = cus_username, email = email
            , password = password, first_name = first_name)
        Member.objects.create(user=cus_user, analyst=ana_user.member, allow_ips=ips, city=city, level=level)
        
        common = ',1xb_xlxxcx:53,1fh_compfuz:53,1fh_comppre:23,1fh_perspre:53,1zskj_bcjq:53,1fy_mbtwo:53,1blxxd:53,TelStatus:53,TelPeriod:53,1qcc_dwtz:5,1qcc_qygjzmhcx:53,1sy_sfztwo:53,1rjh_ltsz:53,1hjxxcx:13,1xb_shsb:13,1zhx_hvvkjzpf:53,1zhx_hvgcfxbq:53,1zhx_hvgjfxbq:13,1ylzc_zfxfxwph:53,1qcc_qydwtz:8,1qcc_qyygdgxtztp:8,1qcc_qyszgxzpcx:8,1qcc_qydwtztp:5,1zskj_idjy:53,1zyhl_ydsj2:53,1blxxb:53,TelCheck:53,1zcx_sxzx:53,1clwz:53,1qyjb:53,1dd:53,EcCateThree:2003,1shbc:2003,1szdj:2003'
        zone = ',1xb_xlxxcx:53,1fh_compfuz:53,1fh_comppre:23,1fh_perspre:53,1zskj_bcjq:53,1fy_mbtwo:53,1blxxd:53,TelStatus:53,TelPeriod:53,1qcc_dwtz:5,1qcc_qygjzmhcx:53,1sy_sfztwo:53,1rjh_ltsz:53,1hjxxcx:13,1xb_shsb:13,1zhx_hvvkjzpf:53,1zhx_hvgcfxbq:53,1zhx_hvgjfxbq:13,1ylzc_zfxfxwph:53,1qcc_qydwtz:8,1qcc_qyygdgxtztp:8,1qcc_qyszgxzpcx:8,1qcc_qydwtztp:5,1zskj_idjy:53,1zyhl_ydsj2:53,1blxxb:53,TelCheck:53,1zcx_sxzx:53,1clwz:53,1qyjb:53,1dd:53,EcCateThree:10003,1shbc:10003,1szdj:10003'
        word = ',1xb_xlxxcx:53,1fh_compfuz:53,1fh_comppre:23,1fh_perspre:53,1zskj_bcjq:53,1fy_mbtwo:53,1blxxd:53,TelStatus:53,TelPeriod:53,1qcc_dwtz:5,1qcc_qygjzmhcx:53,1sy_sfztwo:53,1rjh_ltsz:53,1hjxxcx:13,1xb_shsb:13,1zhx_hvvkjzpf:53,1zhx_hvgcfxbq:53,1zhx_hvgjfxbq:13,1ylzc_zfxfxwph:53,1qcc_qydwtz:8,1qcc_qyygdgxtztp:8,1qcc_qyszgxzpcx:8,1qcc_qydwtztp:5,1zskj_idjy:53,1zyhl_ydsj2:53,1blxxb:53,TelCheck:53,1zcx_sxzx:53,1clwz:53,1qyjb:53,1dd:53,EcCateThree:50003,1shbc:50003,1szdj:50003'

        member = cus_user.member
        if level == '1':
            member.permission = member.permission + word
        elif level == '2':
            member.permission = member.permission + zone
        else:
            member.permission = member.permission + common
        member.save()

    cus_content = '''
        <p>您好！</p>
        <p>以下是贵公司在百融数据测试系统（DTS）的账号基本信息：</p>
        <p>账号：%s 密码：%s</p>
        <p>DTS网址：https://dts.100credit.com/</p>
        <p>您可以登录DTS，将测试数据上传至DTS，完成测试后，分析师会将分析报告发给您。</p>
        <p>为了保证数据安全，DTS采用了IP限制策略，请按照如下方法操作，否则无法登陆：</p>
        <p>1、打开DTS链接，页面上会显示您当前的IP地址；</p>
        <p>2、请将此IP告知与您联系的工作人员，待添加百融白名单后，方可使用。</p>
        <p>系统邮件，请勿回复，谢谢！</p>''' % (cus_username, password)
    send_mail([email], '百融数据测试系统（DTS）账号信息', cus_content)
    return JsonResponse({'msg': 'success'})                
