# -*- coding: utf-8 -*-
import logging
import random
import datetime
import re
import string
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, update_session_auth_hash
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.models import User
from django.contrib import messages

from DTS.views import send_mail
from DTS.mixins import LoginRequiredMixin

from .utils import create_validate_code
from .models import Extra
from .forms import LoginForm, ChangePasswordForm


logger = logging.getLogger('DTS')


class LoginView(TemplateView):
    template_name = 'account/login.html'

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def get(self, request, *args, **kwargs):
        if request.META.get('HTTP_HOST') == 'dts.100credit.com':
            ip = self.get_client_ip(request)
            ip_list = Extra.objects.all()[0].ip_list.split(',')
            if ip in ip_list:
                context = super(LoginView, self).get_context_data(**kwargs)
                context['form'] = LoginForm()
                return self.render_to_response(context)
            else:
                return HttpResponse('您的IP是:%s,不在授权范围以内，请联系与您沟通的工作人员' % ip)
        else:
            context = super(LoginView, self).get_context_data(**kwargs)
            context['form'] = LoginForm()
            return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        form = LoginForm(self, request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            response = redirect('/')
        else:
            messages.info(request, form.non_field_errors().as_text())
            context = super(LoginView, self).get_context_data(**kwargs)
            context['form'] = form
            response = self.render_to_response(context)
        return response


class ForgetPasswordView(TemplateView):
    template_name = 'account/forgetpassword.html'

    def get(self, request, *args, **kwargs):
        context = super(ForgetPasswordView, self).get_context_data(**kwargs)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        validate = request.POST.get('validate')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.info(request, "用户名有误,请重新获取验证码!")
            context = super(ForgetPasswordView, self).get_context_data(**kwargs)
            response = self.render_to_response(context)
        myvalidate = user.member.validate
        now = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        end_time = datetime.datetime.strptime(now, "%Y%m%d%H%M%S")
        start_time = datetime.datetime.strptime(myvalidate[4:], "%Y%m%d%H%M%S")
        interval = (end_time - start_time).seconds
        if not re.match("^(?![a-zA-z]+$)(?!\d+$)(?![!@#$%^&*]+$)[a-zA-Z\d!@#$%^&*]+$", password1) or len(password1) < 6:
            messages.info(request, "密码过于简单!")
            context = super(ForgetPasswordView, self).get_context_data(**kwargs)
            response = self.render_to_response(context)
        elif password1 != password2:
            messages.info(request, "两次密码输入不一致!")
            context = super(ForgetPasswordView, self).get_context_data(**kwargs)
            response = self.render_to_response(context)
        elif validate != myvalidate[:4] or interval > 600:
            messages.info(request, "验证码有误或验证码已过期!")
            context = super(ForgetPasswordView, self).get_context_data(**kwargs)
            response = self.render_to_response(context)
        else:
            user.set_password(password1)
            user.save()
            user.member.validate = ''
            user.member.save()
            response = redirect('/accounts/login/')
        return response


@login_required
def logout_view(request):
    logout(request)
    return redirect('/accounts/login/')


def createvalidate(request):
    mstream = StringIO.StringIO()
    img, code = create_validate_code()
    img.save(mstream, 'GIF')
    request.session['validate'] = code.strip()
    return HttpResponse(mstream.getvalue(), content_type='image/gif')


def getvalidate(request):
    username = request.GET.get('username')
    if not username:
        return JsonResponse({'msg': '用户名不能为空'})
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({'msg': '用户名有误'})
    if not user.email:
        return JsonResponse({'msg': '该用户未绑定邮箱'})
    validate = ''.join([random.choice(string.ascii_letters+string.digits) for _ in range(6)])
    user.member.validate = validate + datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    user.member.save()
    content = """
            <p>您好，</p>
            <p>感谢使用百融金服数据测试服务，您正在测试平台上进行修改密码操作，本次请求的验证码为：%s（为了保障您帐号的安全性，请在10分钟内完成验证。）</p>
            <p>如非本人操作，请检查并确保账户安全。</p>
            <p>系统邮件，请勿回复，谢谢！</p>
            """ % (validate)
    send_mail([user.email], '您正在百融金服数据测试平台（DTS）上进行修改密码操作', content)
    return JsonResponse({'msg': 0, 'email': user.email})


@login_required
def profile_view(request, username):
    return render(request, 'account/profile.html')


class ChangePasswordView(LoginRequiredMixin, TemplateView):
    template_name = 'account/change_pwd.html'

    def get(self, request, *args, **kwargs):
        context = super(ChangePasswordView, self).get_context_data(**kwargs)
        context['form'] = ChangePasswordForm(request.user)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        user = request.user
        form = ChangePasswordForm(user, data=request.POST)

        if form.is_valid():
            new_password = form.cleaned_data['new_password1']
            user.set_password(new_password)
            user.save()
            update_session_auth_hash(request, user)  # 修改密码不使session失效
            return redirect('/accounts/%s/profile/' % request.user.username)
        else:
            error = form.errors.as_data().values()[0][0].messages[-1]
            messages.info(request, error)
            context = super(ChangePasswordView, self).get_context_data(**kwargs)
            context['form'] = form
            return self.render_to_response(context)
