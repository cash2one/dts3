# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import Interface, WTasks


class InterfaceAdmin(admin.ModelAdmin):
    
    list_display = ('name', 'alias')
    search_fields = ['name', 'alias']


class WTasksAdmin(admin.ModelAdmin):
    pass


admin.site.register(Interface, InterfaceAdmin)
admin.site.register(WTasks, WTasksAdmin)
