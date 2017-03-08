# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import xlrd
import time
import logging
import traceback
import chardet

from django.shortcuts import get_object_or_404
from django.views.generic import ListView, TemplateView
from django.core.urlresolvers import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponseNotFound, JsonResponse, Http404
from django.db import transaction

from DTS.mixins import LoginRequiredMixin
from DTS.views import send_mail
from analyst.models import ReportFile

from .models import SourceFile


logger = logging.getLogger('DTS')


class FileListView(LoginRequiredMixin, ListView):

    paginate_by = 18
    context_object_name = 'files'
    template_name = 'customer/file_list.html'

    def get_queryset(self):
        if self.request.user.member.role != 1:
            raise Http404
        member = self.request.user.member
        self.filename = self.request.GET.get('filename', '')
        if self.filename:
            return SourceFile.objects.filter(custom=member, filename__contains=self.filename)
        return SourceFile.objects.filter(custom=member)

    def get_context_data(self, **kwargs):
        context = super(FileListView, self).get_context_data(**kwargs)
        context['filename'] = self.filename
        return context


class UpFileView(LoginRequiredMixin, TemplateView):
    # template_name = 'customer/file_list.html'
    success_url = reverse_lazy('cus_file_list')
    # permission_required = 'sourcefile.add_task'

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(UpFileView, self).dispatch(request, *args, **kwargs)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        if not request.is_ajax():
            return HttpResponseNotFound
        file = request.FILES.get('sourcefile', '')
        extra_info = request.POST.get('extra_info','')
        if not file:
            return JsonResponse({'msg': '请上传一个文件'})

        basename, suffix = os.path.splitext(file.name)
        if suffix not in ['.txt', '.xlsx', '.xls', '.csv']:
            return JsonResponse({'msg':'文件格式必须为txt,xlsx,xls,csv'})
        if suffix in ['.xls', '.xlsx']:
            excel = xlrd.open_workbook(file.temporary_file_path())
            sheet = excel.sheet_by_index(0)
            total_lines = sheet.nrows
            try:
                head = ','.join(sheet.row_values(0))
            except:
                logger.error('上传excel文件失败'+traceback.format_exc())
                return JsonResponse({"msg":"文件格式有误或编码错误"})
        else:
            try:
                head = file.readline().strip('\n')
                head.split(',')
            except:
                return JsonResponse({"msg":"文件格式有误或编码错误"})
            total_lines = len(file.readlines()) + 1

        if total_lines > 400000:
            return JsonResponse({'msg': '文件行数不能超过400000'})

        if total_lines < 2:
            return JsonResponse({'msg': '文件内容不能为空'})


        analyst = request.user.member.analyst
        email = analyst.user.email

        content = """
        <p>你好，你的客户%s上传了一份文件(文件名:%s)，请登陆<a href="https://dts.100credit.com">DTS系统</a>查看。</p>
        <p>系统邮件，请勿回复，谢谢！</p>
        """ % (request.user.first_name, file.name)

        send_mail([email],'您有客户上传测试文件', content)
        sf = SourceFile(custom=request.user.member, filename=file, extra_info=extra_info,
                        file_size=file.size, total_lines=total_lines, head=head)
        filename = '_'.join([request.user.first_name, basename, time.strftime('%Y%m%d-%H%M')]) + suffix
        sf.filename.save(filename, file)
        sf.save()
        logging.info(request.user.first_name+"上传了文件：" + file.name)
        return JsonResponse({'msg': '0'})


class ReportFileListView(LoginRequiredMixin, ListView):

    paginate_by = 18
    template_name = 'customer/reportfile_list.html'

    def get_queryset(self):
        print self.request.user.member.role
        if self.request.user.member.role != 1:
            raise Http404
        pk = self.kwargs['pk']
        sf = get_object_or_404(SourceFile, pk=int(pk))
        return ReportFile.objects.filter(source_file=sf)
