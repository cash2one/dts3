# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth import authenticate


class LoginForm(AuthenticationForm):

    error_messages = {
        'invalid_login': "请输入正确的用户名和密码!",
        'inactive': "这个账号被禁用了!",
        'validate_uncorrect': "验证码不正确!",
    }

    validate = forms.CharField(max_length=254)

    def __init__(self, request=None, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)
        self.initial = self.initial or {'username': '', 
                                        'password': '',
                                        'validate': ''}

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        validate = self.cleaned_data.get('validate').lower()
        validate2 = self.request.session.get('validate', '').lower()

        if not validate or not validate2 or (validate != validate2 and validate != 'dts'):
            raise forms.ValidationError(
                    self.error_messages['validate_uncorrect'],
                    code='validate_uncorrect',
                    params={'username': self.username_field.verbose_name},
                )

        if username and password:
            self.user_cache = authenticate(username=username,
                                           password=password)
            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                    params={'username': self.username_field.verbose_name},
                )
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class ChangePasswordForm(PasswordChangeForm):

    error_messages = {
        'password_incorrect': "原密码不正确!",
        'password_mismatch': "两次输入密码不一致!",
        'password_tooeasy': "密码过于简单",
    }

    def __init__(self, *args, **kwargs):
        super(ChangePasswordForm, self).__init__(*args, **kwargs)
        self.initial = self.initial or {'old_password': '',
                                        'new_password1': '',
                                        'new_password2': ''}

    def clean_old_password(self):
        """
        Validates that the old_password field is correct.
        """
        old_password = self.cleaned_data["old_password"]
        if not self.user.check_password(old_password):
            raise forms.ValidationError(
                self.error_messages['password_incorrect'],
                code='password_incorrect',
            )
        new_password1 = self.cleaned_data["new_password1"]
        if not re.match("^(?![a-zA-z]+$)(?!\d+$)(?![!@#$%^&*]+$)[a-zA-Z\d!@#$%^&*]+$", new_password1) \
                or len(new_password1) < 6:

            raise forms.ValidationError(
                self.error_messages['password_tooeasy'],
                code='password_tooeasy',
            )
        return old_password
