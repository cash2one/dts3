#!/usr/bin/env bash

nohup celery worker -A DTS -l info --concurrency=2 -n worker-default@%h -Q default > ../worker-default.log 2>&1 &
sleep 1
nohup celery worker -A DTS -l info --concurrency=2 -n worker-hx@%h -Q hx > ../worker-hx.log 2>&1 &
sleep 1
nohup celery worker -A DTS -l info --concurrency=2 -n worker-ice@%h -Q ice > ../worker-ice.log 2>&1 &
sleep 1
# 导文件的worker只在web服务器上运行
nohup celery worker -A DTS -l info --concurrency=1 -n worker-export-file@%h -Q export_to_file > ../worker-export-file 2>&1 &
sleep 1
nohup celery worker -A DTS -l info --concurrency=1 -n worker-scan@%h -Q scan > ../worker-scan 2>&1 &
