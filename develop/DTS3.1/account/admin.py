# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import Member, Queryer, Extra


@admin.register(Extra)
class CommentAdmin(admin.ModelAdmin):
    pass


class MemberInline(admin.StackedInline):
    model = Member
    fk_name = 'user'
    can_delete = False
    verbose_name_plural = u'成员信息列表'


class CustomUserAdmin(UserAdmin):
    inlines = (MemberInline,)
    list_display = ('username', 'first_name', 'email', 'role')
    list_filter = ('member__role',)
    search_fields = ['username', 'email', 'first_name']

    def role(self, obj):
        return obj.member.get_role_display()
    role.short_description = u'角色'


class QueryerAdmin(admin.ModelAdmin):
    list_display = ('member', 'apicode','username', 'password')
    search_fields = ['apicode', 'member']


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Queryer, QueryerAdmin)
