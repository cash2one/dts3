# -*- coding: utf-8 -*-
from __future__ import absolute_import

from kombu import Queue
# from kombu.common import Broadcast
from celery.schedules import crontab


broker_url = 'amqp://guest:guest@localhost:5672//'

result_backend = 'redis://localhost:6379/0'

task_serializer = 'msgpack'

result_serializer = 'json'

result_expires = 60 * 60 * 8  # 结果过期时间

accept_content = ['json', 'msgpack']  # 指定接受的内容类型

timezone = 'Asia/Shanghai'

enable_utc = True

# ignore_result = True

worker_concurrency = 2

worker_prefetch_multiplier = 2

worker_max_tasks_per_child = 100

# worker_max_memory_per_child = 128 * 1024

# 指定导入的任务模块
imports = (
    'analyst.tasks',
)

beat_schedule = {
    'every-3-minute': {
        'task': 'taskfor_scan',
        'schedule': crontab(minute='*/3'),
        'args': ()
    },
}

task_queues = (
    Queue('default'),
    Queue('export_to_file'),
    Queue('scan'),

    # 此处先用Queue配置, 即一个任务只有一个worker在执行, 这样可以同时跑多一些任务.
    # 如果需要对任务速度进行提升, 可以用Broadcast进行配置.
    # 这样可以多个worker共同执行一个任务, 但同时执行的任务数会减少.
    Queue('hx'),
    Queue('ice'),
)

task_create_missing_queues = True
task_default_exchange = 'default'
task_default_queue = 'default'  # 默认的队列, 如果一个消息不符合其他的队列就会放在默认队列里面
task_default_exchange_type = 'direct'
task_default_routing_key = 'task.default'


task_routes = {
    'taskfor_ice': {'queue': 'ice'},
    'taskfor_hx': {'queue': 'hx'},

    'export_hx_result_to_file': {'queue': 'export_to_file'},
    'export_ice_result_to_file': {'queue': 'export_to_file'},

    'taskfor_scan': {'queue': 'scan'},
}
