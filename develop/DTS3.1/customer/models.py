# -*- coding: utf-8 -*-
import os

from django.db import models
from account.models import Member
from django.core.urlresolvers import reverse


class SourceFile(models.Model):
    custom = models.ForeignKey(Member, limit_choices_to={'member__role': 1})
    # can_down = models.ManyToManyField(Member, related_name='down_sourcefile')
    # file_source_type = models.CharField(max_length=40, null=True, blank=True, choices=FILE_SOURCE_TYPES)
    # guarantee_type = models.CharField(max_length=40, null=True, blank=True, choices=GUARANTEE_TYPE)
    # user_type = models.CharField(max_length=40, null=True, blank=True, choices=USER_TYPE)
    filename = models.FileField(max_length=800, upload_to='source_file/%Y/%m')
    # file_from = models.CharField(max_length=100)
    extra_info = models.CharField(max_length=300, default='', blank=True)
    # is_done = models.BooleanField(default=False)
    fields = models.CharField(max_length=1000, default='', blank=True, verbose_name='标注字段')
    head = models.CharField(max_length=1000, default='', blank=True, verbose_name='文件表头')
    # skip_lines = models.IntegerField(max_length=4, null=True, blank=True)
    # splitor = models.CharField(max_length=10, null=True, blank=True)
    # is_checked = models.BooleanField(default=False)
    # is_saved_db = models.BooleanField(default=False)
    total_lines = models.IntegerField(default=0)
    file_size = models.IntegerField(default=0)
    # id_num = models.IntegerField(max_length=4, null=True, blank=True)
    # is_sampling = models.BooleanField(default=False, verbose_name='是否已加入数据集市')
    # is_delete = models.BooleanField(default=False, verbose_name="是否被删除")
    # mail_num = models.IntegerField(max_length=4, null=True, blank=True)
    # is_applied = models.BooleanField(default=False)
    # applied_done_time = models.DateTimeField(null=True, blank=True)
    # is_has_new = models.BooleanField(default=False)
    # can_delete = models.BooleanField(default=False)
    # sampling_sort = models.CharField(max_length=20, null=True, blank=True, verbose_name='该客户在数据集市的文件个数')
    # loan_amount = models.CharField(max_length=200, null=True, blank=True, verbose_name='贷款产品额度')
    # loan_deadline = models.CharField(max_length=200, null=True, blank=True, verbose_name="贷款产品期限")
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '源文件'
        verbose_name_plural = '源文件列表'
        permissions = (
            ('assign_cus', 'Can assign customer'),
            ('assign_che', 'Can assign checker'),
        )
        ordering = ['-create_time']

    def __unicode__(self):
        return u'%s' % os.path.basename(self.filename.name)

    def mappingfiles_exists(self):
        return self.mappingedfile_set.exists()

    def get_absolute_url(self):
        return reverse('cus_reportfile_list', kwargs={'pk': self.pk})
