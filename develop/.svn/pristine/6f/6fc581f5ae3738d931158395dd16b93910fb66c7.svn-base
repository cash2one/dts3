# -*- coding:utf-8 -*-
import xlrd
import redis
import datetime
import os
import json


def redisconn():
    pool = redis.ConnectionPool(host='127.0.0.1', port=6379)
    conn = redis.Redis(connection_pool=pool)
    return conn


def iter_xls(file):
    excel = xlrd.open_workbook(file)
    sheet = excel.sheet_by_index(0)
    for rownum in xrange(sheet.nrows):
        tl = []
        temp = sheet.row_values(rownum)
        for k in range(len(temp)):
            if type(temp[k]) is float:
                if 17899 < int(temp[k]) < 55134:
                    date_time = datetime.date.fromordinal(datetime.date(1899, 12, 31).toordinal()-1+int(temp[k])).strftime("%Y-%m-%d")
                    tl.append(date_time)
                else:
                    tl.append(str(temp[k]).split(".")[0])
            elif type(temp[k]) is int:
                tl.append(str(temp[k]))
            else:
                tl.append(temp[k])
        yield ','.join(tl)


class FileReader(object):
    """reader for src_file"""
    def __init__(self, file, username):
        self.filepath = file.filename.path
        self.fields = file.fields.split(',')
        self.username = username
        self.length = file.total_lines

    def exist(self):
        return os.path.exists(self.filepath)

    def read_filedata(self):
        _, ext = os.path.splitext(self.filepath)
        if ext == '.xls' or ext == '.xlsx':
            lines = iter_xls(self.filepath)
            lines.next()
        else:
            with open(self.filepath, 'r') as f:
                lines = f.readlines()
            lines = lines[1:]
        filedata = [line.strip().split(',') for line in lines]
        return filedata

    def tansform_filedata(self, filedata):
        conn = redisconn()
        conn.delete(self.username)
        conn.delete(self.username+'_res')
        conn.rpush(self.username, *[json.dumps(dict(zip(self.fields, x))) for x in filedata])
        conn.rpush(self.username+'_res', *['' for _ in xrange(self.length)])
        return self.username
