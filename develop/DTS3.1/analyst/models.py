# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os

from django.db import models
from django.core.urlresolvers import reverse

from customer.models import SourceFile
from account.models import Member


class ReportFile(models.Model):
    report_file = models.FileField(upload_to='report_file/%Y/%m')
    source_file = models.ForeignKey(SourceFile, null=True, blank=True)
    customer = models.ForeignKey(Member, limit_choices_to={'member__role': 1}, null=True, blank=True)
    file_desc = models.CharField(max_length=300, default='', blank=True)
    file_size = models.IntegerField()
    passwd = models.CharField(max_length=10)
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '报告文件'
        verbose_name_plural = '报告文件列表'
        ordering = ['-create_time']

    def __unicode__(self):
        return u'%s' % os.path.basename(self.report_file.name)

    def get_absolute_url(self):
        return reverse('ana_reportfile_list', kwargs={'pk': self.pk})


class MappingedFile(models.Model):
    source_file = models.ForeignKey(SourceFile, null=True, blank=True)
    # can_down = models.ForeignKey(Member, related_name='down_mappedfile')
    # uploader = models.ForeignKey(Member, related_name='mappingedfile_uploaders', null=True, blank=True)
    member = models.ForeignKey(Member, limit_choices_to={'member__role': 2}, null=True, blank=True)
    # parent_file = models.ForeignKey(ThirdMappedFile, null=True, blank=True)
    file = models.FileField(max_length=500, upload_to='mappinged_file/%Y/%m')
    file_size = models.IntegerField()
    mapinter = models.CharField(max_length=800, default='', blank=True, verbose_name='匹配接口')
    # is_cus_visible = models.BooleanField(default=True, verbose_name='客户是否可见')
    # is_third_file = models.BooleanField(default=False, verbose_name='是否为第三方文件')
    # is_csv = models.BooleanField(default=False, verbose_name='是否为csv文件')
    # is_crypt = models.BooleanField(default=False)
    # id_num = models.IntegerField(max_length=4, null=True, blank=True)
    # cell_num = models.IntegerField(max_length=4, null=True, blank=True)
    # mail_num = models.CharField(max_length=40, null=True, blank=True)
    # password = models.CharField(max_length=50, null =True, blank=True)
    # is_haina = models.BooleanField(default=False, verbose_name='是否画像接口匹配')
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mapping输出文件'
        verbose_name_plural = 'Mapping输出文件列表'
        ordering = ['-create_time']

    def __unicode__(self):
        return '%s' % os.path.basename(self.file.name)


class Interface(models.Model):
    name = models.CharField(max_length=100, verbose_name='英文')
    alias = models.CharField(max_length=120, verbose_name='中文')  # change name
    # create_time = models.DateTimeField(auto_now_add=True)
    thread_num = models.IntegerField(default=10, verbose_name='并发数')
    # max_map = models.IntegerField(default=0, verbose_name='最大匹配量')
    fields = models.TextField(max_length=65535, default='', blank=True, verbose_name='必要字段')
    filehead = models.TextField(max_length=65535, default='', blank=True, verbose_name='表头')

    class Meta:
        verbose_name = '接口名称'
        verbose_name_plural = '接口名称列表'

    def __unicode__(self):
        return self.name


class WTasks(models.Model):
    username = models.CharField(max_length=100, default='', blank=True)
    modal = models.CharField(max_length=100, default='', blank=True)
    fileid = models.IntegerField(default=0)
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '任务'
        verbose_name_plural = '任务列表'

    def __unicode__(self):
        return self.username
