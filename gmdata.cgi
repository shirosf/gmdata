#!/usr/bin/python3
# -*- coding: utf-8 -*-
import getopt
import datetime, sys, time, os
from TwitterAPI import TwitterAPI
from twitter_keys import API_KEY, API_KEY_SECRET, ACCSESS_TOKEN, ACCSESS_TOKEN_SECRET
import pytz
import sqlite3
import numpy
import cgi
import cgitb; cgitb.enable()

startdate=""
enddate=""
maxval=""
minval=""

class GetTweet():
    tid_Apr1='186105590563606528'
    def __init__(self, user='gmdata'):
        self.gmdata_user='gmdata'

    def get_dt(self,tstr):
            astr=tstr.replace('+0000 ','')
            dt=datetime.datetime.strptime(astr, '%a %b %d %H:%M:%S %Y')
            dt=dt.replace(tzinfo=pytz.timezone('UTC'))
            dt=dt.astimezone(pytz.timezone('Asia/Tokyo'))
            return dt

    def get_last_htweet(self):
        tapi=TwitterAPI(API_KEY, API_KEY_SECRET, ACCSESS_TOKEN, ACCSESS_TOKEN_SECRET)
        tls=tapi.request('statuses/home_timeline', {'count':'2'})
        for tl in tls.get_iterator():
            dt=self.get_dt(tl['created_at'])
            items=tl['text'].split()
            if items[0]!='last24H': continue
            try:
                v=int(items[2])
            except:
                print("error:",sys.exc_info()[0])
                print(tl.text)
                v=0
            return dt,v
        return None

    def get_htweet_since(self, since_id=None, count=100):
        if since_id==None:
            since_id=self.tid_Apr1
        tapi=TwitterAPI(API_KEY, API_KEY_SECRET, ACCSESS_TOKEN, ACCSESS_TOKEN_SECRET)
        tls=tapi.request('statuses/home_timeline', {'since_id':'%s' % since_id,
                                                    'count':'%d' % count})
        res=[]
        for tl in tls:
            dt=self.get_dt(tl['created_at'])
            items=tl['text'].split()
            if items[0]!='last24H': continue
            try:
                v=int(items[2])
            except:
                print("error:",sys.exc_info()[0])
                print(tl.text)
                v=0
            res.append((dt,v))
        return res

    def get_last_dtweet(self):
        tapi=TwitterAPI(API_KEY, API_KEY_SECRET, ACCSESS_TOKEN, ACCSESS_TOKEN_SECRET)
        tls=tapi.request('statuses/home_timeline', {'count':'24'})
        for tl in tls:
            dt=self.get_dt(tl['created_at'])
            items=tl['text'].split()
            if items[0]!='last16Days': continue
            try:
                v=int(items[2])
            except:
                print("error:",sys.exc_info()[0])
                print(tl.text)
                v=0
            return dt,v
        return None


def adapt_datetime(ts):
    return int(time.mktime(ts.timetuple()))
class ManageDb():
    def __init__(self, dbname='%s/gmdata.db' % os.path.dirname(sys.argv[0]),
                 tbname='gmdata'):
        self.db=sqlite3.connect(dbname)
        self.tbname=tbname
        self.cur=self.db.cursor()
        self.cur.execute("CREATE TABLE IF NOT EXISTS %s(datetime INT, value INT)"
                         % self.tbname)
        sqlite3.register_adapter(datetime.datetime, adapt_datetime)

    def get_value(self, dt):
        self.cur.execute("SELECT value FROM %s WHERE datetime=?" % (self.tbname),
                         (dt,))
        self.db.commit()
        row=self.cur.fetchone()
        if not row: return None
        return row[0]

    def get_values(self, fdt, tdt, skip_lt=None, skip_gt=None):
        self.cur.execute("SELECT * FROM %s WHERE datetime BETWEEN ? AND ? ORDER BY datetime" \
                         % (self.tbname),(fdt,tdt))
        self.db.commit()
        res=[]
        while True:
            row=self.cur.fetchone()
            if not row: return res
            if skip_lt and row[1]<skip_lt: continue
            if skip_gt and row[1]>skip_gt: continue
            res.append((row[0],row[1]))

    def put_value(self,dt,v):
        if self.get_value(dt): return -1
        self.cur.execute("INSERT INTO %s VALUES(?, ?)" % (self.tbname), (dt, v))
        self.db.commit()
        return 0;

    def delete_values(self, fdt, tdt):
        self.cur.execute("DELETE FROM %s WHERE datetime BETWEEN ? AND ?" \
                         % (self.tbname),(fdt,tdt))
        self.db.commit()

def moving_average(tds, mva):
    res=[]
    for i in range(mva-1,len(tds)):
        v=numpy.average([j[1] for j in tds[i-mva+1:i+1]])
        res.append((tds[i][0],v))
    return res

def print_html(db, fdt, tdt, skip_lt=None, skip_gt=None, mva=0):
    tds=db.get_values(fdt,tdt,skip_lt,skip_gt)

    avg=numpy.average([i[1] for i in tds])
    std=numpy.std([i[1] for i in tds])
    if mva>1: tds=moving_average(tds,mva)
    print("Content-Type: text/html")
    print()
    print ("""
<html>
  <head>
    <meta http-equiv="Content-type" content="text/html; charset=utf-8" />
    <link href="calendar.css" type="text/css" rel="stylesheet" />
    <script src="http://openjs.com/js/jsl.js" type="text/javascript"></script>
    <script src="http://openjs.com/common.js" type="text/javascript"></script>
    <script src="calendar.js" type="text/javascript"></script>
    <script type="text/javascript">
    function init() {
        calendar.set("startdate");
        calendar.set("enddate");
    }
    </script>
    <script type="text/javascript" src="https://www.google.com/jsapi"></script>
    </script>
    <script type="text/javascript">
      google.load("visualization", "1", {packages:["corechart"]});
      google.setOnLoadCallback(drawChart);
      function drawChart() {
        var data = new google.visualization.DataTable();
        data.addColumn('datetime', 'date');
        data.addColumn('number', 'value');
        data.addRows([
""")
    for t,v in tds:
        t=time.localtime(t)
        print("[new Date(%d,%d,%d,%d,%d,0), %d]," %\
              (t.tm_year,t.tm_mon-1,t.tm_mday,t.tm_hour,t.tm_min,v))

    print("""
        ]);

        var options = {
          title: '八王子放射線 GM管:LND712, 縦軸:CPH',
          legend: {position: 'none'},
          hAxis: {format:'M/d H時'},
        };

        var chart = new google.visualization.LineChart(document.getElementById('chart_div'));
        chart.draw(data, options);
      }
    </script>
  </head>
  <body>
    <div id="chart_div" style="width: 900px; height: 500px;"></div>
""")
    print("表示範囲平均値=%.01f<br/>" % avg)
    print("表示範囲標準偏差=%.01f<br/>" % std)
    print('<form action="" method="post">')
    print('<label for="startdate">表示開始日</label>')
    print('<input type="text" name="startdate" id="startdate" value="%s" />' % startdate)
    print('<label for="enddate">表示終了日</label>')
    print('<input type="text" name="enddate" id="enddate" value="%s" /><br/>' % enddate)
    print('最大値（これより大きな数値は無視）: '\
    '<input type="text" name="maxval" value="%s" /><br/>' % maxval)
    print('最小値（これより小さな数値は無視）: '\
    '<input type="text" name="minval" value="%s" /><br/>' % minval)
    print('<input type="submit" name="redraw" value="再表示" />')
    print('</form>')
    print('</body></html>')


def print_data(db, fdt, tdt, skip_lt=None, skip_gt=None, mva=0):
    tds=db.get_values(fdt,tdt,skip_lt,skip_gt)
    if mva>1: tds=moving_average(tds,mva)
    for t,v in tds:
        t=time.localtime(t)
        print("%02d月%02d日 %02d時%02d分"%(t.tm_mon,t.tm_mday,t.tm_hour,t.tm_min), v)
    print("平均=%02f" % numpy.average([i[1] for i in tds]))
    print("標準偏差=%02f" % numpy.std([i[1] for i in tds]))

def print_test(gt, db, fdt, tdt):
    tds=gt.get_htweet_since()
    for d in tds:
        print(d[0], d[1])

def usage(a=None):
    if a: print(a)
    print("-g|--get: fetch the latest data")
    print("-s id|--since=id: fetch 100 data since id")
    print("-p|--print: print data")
    print("-w|--web:print html")
    print("-f 'Y-M-D_H:M'|--from='Y-M-D_H:M'")
    print("-t 'Y-M-D_H:M'|--to='Y-M-D_H:M'")
    print("-l value|--skiplt=value: skip less than this value")
    print("-g value|--skipgt=value: skip greater than this value")
    print("-d|--delete: delete values, requires -f and -t options")
    print("-a num|--mva=num: use moving average with 'num' samples")
    return 1


def cgi_fields(argv):
    global startdate, enddate, maxval, minval

    argv.append('form')
    argv.append('-w')
    form = cgi.FieldStorage()
    v=form.getvalue("since_date",None)
    if not v:
        startdate=form.getvalue("startdate","")
        if startdate: v=startdate+"_00:00"
    if v: argv.append("--from=%s" % v)
    v=form.getvalue("to_date",None)
    if not v:
        enddate=form.getvalue("enddate","")
        if enddate: v=enddate+"_23:59"
    if v: argv.append("--to=%s" % v)
    v=form.getvalue("skiplt",None)
    if not v:
        minval=form.getvalue("minval","")
        if minval: v=minval
    if v: argv.append("--skiplt=%s" % v)
    v=form.getvalue("skipgt",None)
    if not v:
        maxval=form.getvalue("maxval","")
        if maxval: v=maxval
    if v: argv.append("--skipgt=%s" % v)
    v=form.getvalue("mva",None)
    if v: argv.append("--mva=%s" % v)
    return

if __name__ == "__main__":
    argv=[]
    if len(sys.argv)>1:
        argv=sys.argv
    else:
        cgi_fields(argv)

    try:
        opts, args = getopt.getopt(argv[1:], "gpwf:t:s:0l:g:da:",
              ["get","print","web","from=","to=","help","test",
               "since=","skiplt=","skipgt=","delete","mva="])
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    runmode=None
    fdt_exist=tdt_exist=False
    tdt=datetime.datetime.now()
    fdt=tdt-datetime.timedelta(10)
    sid=None
    skiplt=None
    skipgt=None
    mva=0
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        if o in ("-f", "--from"):
            try:
                fdt=datetime.datetime.strptime(a, '%Y-%m-%d_%H:%M')
                fdt_exist=True
            except:
                sys.exit(usage("'%s' must be 'Y-m-d_H:M' format" % a))

        if o in ("-t", "--to"):
            try:
                tdt=datetime.datetime.strptime(a, '%Y-%m-%d_%H:%M')
                tdt_exist=True
            except:
                sys.exit(usage("'%s' must be 'Y-m-d_H:M' format" % a))

        if o in ("-g", "--get"):
            runmode="get"
        if o in ("-w", "--web"):
            runmode="web"
        if o in ("-p", "--print"):
            runmode="print"
        if o in ("-0", "--test"):
            runmode="test"
        if o in ("-s", "--since"):
            if a!="0":
                sid=a
            runmode="since"
        if o in ("-d", "--delete"):
            runmode="delete"
        if o in ("-l", "--skiplt"): skiplt=int(a)
        if o in ("-g", "--skipgt"): skipgt=int(a)
        if o in ("-a", "--mva"): mva=int(a)

    if not runmode: sys.exit(usage())

    gt=GetTweet()
    db=ManageDb()

    if runmode=="test":
        print_test(gt, db, fdt, tdt)

    if runmode=="print":
        print_data(db, fdt, tdt, skiplt, skipgt, mva)

    if runmode=="web":
        print_html(db, fdt, tdt, skiplt, skipgt, mva)

    if runmode=="get":
        d=gt.get_last_htweet()
        if not d: sys.exit(-1)
        db.put_value(d[0],d[1])

    if runmode=="since":
        tds=gt.get_htweet_since(since_id=sid)
        for d in tds:
            db.put_value(d[0],d[1])

    if runmode=="delete":
        if not (fdt_exist and tdt_exist):
            print("to delete need '-f' and '-t' options")
            sys.exit(-1)

        print("delete from '%s' to '%s'" % (fdt,tdt))
        s=raw_input("Are you sure (yes/no) ? ")
        if s=='yes':
            db.delete_values(fdt, tdt)
