# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.contrib.auth.models import User


class Member(models.Model):
    ROLE = (
        (0, '数据检查'),
        (1, '客户'),
        (2, '分析师'),
    )
    user = models.OneToOneField(User)
    analyst = models.ForeignKey('Member', related_name='member_analyst', limit_choices_to={'role': 2},
                                blank=True, null=True, on_delete=models.SET_NULL)
    checker = models.OneToOneField('Member', related_name='member_checker', limit_choices_to={'role': 0},
                                   blank=True, null=True, on_delete=models.SET_NULL)
    role = models.IntegerField(choices=ROLE, default=1)
    allow_ips = models.TextField(max_length=800, default='', blank=True)
    permission = models.TextField(max_length=65535, default='', blank=True, verbose_name='接口权限', help_text='接口名称：匹配数量')
    ty3 = models.TextField(max_length=65535, default='', blank=True, verbose_name='通用3权限', help_text='接口名称：匹配数量')
    xd3 = models.TextField(max_length=65535, default='', blank=True, verbose_name='信贷3权限', help_text='接口名称：匹配数量')
    ty4 = models.TextField(max_length=65535, default='', blank=True, verbose_name='通用4权限', help_text='接口名称：匹配数量')
    xd4 = models.TextField(max_length=65535, default='', blank=True, verbose_name='信贷4权限', help_text='接口名称：匹配数量')
    apicodes = models.CharField(max_length=200, default='', blank=True)
    level = models.CharField(max_length=100, default='', blank=True, verbose_name='客户级别')
    city = models.CharField(max_length=50, default='', blank=True, verbose_name='客户总部所在城市')
    validate = models.CharField(max_length=50, default='', blank=True, verbose_name='验证码')

    class Meta:
        verbose_name = "系统成员"
        verbose_name_plural = "成员列表"

    def __unicode__(self):
        return self.user.first_name


class Queryer(models.Model):
    member = models.OneToOneField(Member, null=True, blank=True, limit_choices_to={'role': 2}, verbose_name='分析师')
    username = models.CharField(max_length=50, default='', blank=True)
    password = models.CharField(max_length=20, default='', blank=True)
    apicode = models.CharField(max_length=20, default='', blank=True)
    is_busy = models.BooleanField(default=False)
    fileid = models.IntegerField(default=0, verbose_name='源文件')
    taskid = models.CharField(max_length=200, default='', blank=True, verbose_name='taskid')
    mapinter = models.CharField(max_length=500, default='', blank=True, verbose_name='匹配接口')
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "画像帐号"
        verbose_name_plural = "画像帐号列表"

    def __unicode__(self):
        return self.apicode


class Extra(models.Model):
    ips = models.TextField(max_length=65535, default='', blank=True, verbose_name='客户白名单')

    class Meta:
        verbose_name = "白名单"
        verbose_name_plural = "白名单列表"

    def __unicode__(self):
        return self.ip_list
