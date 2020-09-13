#!/usr/bin/python3
import pyaudio
import wave
import sys
import getopt
from datetime import datetime
from threading import Thread
import shelve
from TwitterAPI import TwitterAPI
from twitter_keys import API_KEY, API_KEY_SECRET, ACCSESS_TOKEN, ACCSESS_TOKEN_SECRET
import serial
import socket
import select
import signal
import time

HISTORY_DATA_FILE = '.gmdata_history'
thr_upper = 0x40
thr_lower = 0x5
thr_cont_times = 10
cont_reset = 5
debug_print = False
udp_port = 5001
udpcon = None
terminate_program=0

class UdpConsole():
    wrfd=sys.stdout
    sender=None

    def __init__(self, port=udp_port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('',port))

    def udpcon_read(self, prompt):
        rlist=[self.sock, sys.stdin]
        self.udpcon_write(prompt)
        try:
            reads, dws, des = select.select(rlist,[],[])
        except:
            if terminate_program==0:
                print("error:",sys.exc_info()[0])
            return 'q'

        for rfd in reads:
            if rfd == self.sock:
                rdata,self.sender=rfd.recvfrom(16)
                return rdata.decode('utf-8')
            if rfd == sys.stdin:
                rdata=sys.stdin.readline()
                self.sender=None
                return rdata
        return ""

    def udpcon_write(self, data):
        if self.sender==None:
            sys.stdout.write(data)
            sys.stdout.flush()
        else:
            self.sock.sendto(data.encode('utf-8'), self.sender)


class TwitterTweet(Thread):
    def __init__(self, msg='', encoding = 'utf-8'):
        Thread.__init__(self)
        self.msg=msg
        self.encoding=encoding

    def create_msg(self, gmdata):
        self.msg='last24H N2O:'
        for i in range(3):
            self.msg = "%s %4d %4d %4d %4d %4d %4d %4d %4d" % (
                self.msg,
                gmdata.hhistory[i*8+0],
                gmdata.hhistory[i*8+1],
                gmdata.hhistory[i*8+2],
                gmdata.hhistory[i*8+3],
                gmdata.hhistory[i*8+4],
                gmdata.hhistory[i*8+5],
                gmdata.hhistory[i*8+6],
                gmdata.hhistory[i*8+7])

    def create_dmsg(self, gmdata):
        self.msg='last16Days N2O:'
        for i in range(2):
            self.msg = "%s %5d %5d %5d %5d %5d %5d %5d %5d" % (
                self.msg,
                gmdata.dhistory[i*8+0],
                gmdata.dhistory[i*8+1],
                gmdata.dhistory[i*8+2],
                gmdata.dhistory[i*8+3],
                gmdata.dhistory[i*8+4],
                gmdata.dhistory[i*8+5],
                gmdata.dhistory[i*8+6],
                gmdata.dhistory[i*8+7])

    def run(self):
        api=TwitterAPI(API_KEY, API_KEY_SECRET, ACCSESS_TOKEN, ACCSESS_TOKEN_SECRET)
        status = api.request('statuses/update', {'status': self.msg})
        udpcon.udpcon_write("status %s:%s\n" % (status.status_code, self.msg))


class GMDataHistory():
    mhistory=[]
    hhistory=[]
    dhistory=[]
    twpost=False
    mcount_div=1
    def __init__(self):
        tv=datetime.now()
        self.cont=0
        self.discont=0
        self.lminute=tv.minute
        self.lhour=tv.hour
        self.lday=tv.day

        self.shelf=shelve.open(HISTORY_DATA_FILE)

        if 'dcount' in self.shelf:
            self.dcount=self.shelf['dcount']
        else:
            self.dcount=0

        if 'hcount' in self.shelf:
            self.hcount=self.shelf['hcount']
        else:
            self.hcount=0

        if 'mcount' in self.shelf:
            self.mcount=self.shelf['mcount']
        else:
            self.mcount=0

        if 'mhistory' in self.shelf:
            self.mhistory=self.shelf['mhistory']
        else:
            for i in range(60):
                self.mhistory.append(0)

        if 'hhistory' in self.shelf:
            self.hhistory=self.shelf['hhistory']
        else:
            for i in range(24):
                self.hhistory.append(0)

        if 'dhistory' in self.shelf:
            self.dhistory=self.shelf['dhistory']
        else:
            for i in range(365):
                self.dhistory.append(0)

    def close(self):
        self.shelf['mhistory']=self.mhistory
        self.shelf['hhistory']=self.hhistory
        self.shelf['dhistory']=self.dhistory
        self.shelf['dcount']=self.dcount
        self.shelf['hcount']=self.hcount
        self.shelf['mcount']=self.mcount
        self.shelf.close()

    def update_mhistory(self, minute):
        self.lminute=minute
        self.mhistory.pop()
        self.mcount //= self.mcount_div
        self.mhistory.insert(0, self.mcount)
        self.hcount+=self.mcount
        self.mcount=0

    def update_hhistory(self, hour):
        self.lhour=hour
        self.hhistory.pop()
        self.hhistory.insert(0, self.hcount)
        self.dcount+=self.hcount
        self.hcount=0
        if self.twpost:
            tw=TwitterTweet()
            tw.create_msg(self)
            tw.start()

    def update_dhistory(self, day):
        self.lday=day
        self.dhistory.pop()
        self.dhistory.insert(0, self.dcount)
        self.dcount=0
        if self.twpost:
            tw=TwitterTweet()
            tw.create_dmsg(self)
            tw.start()

    def data_update(self, wait_minute=False):
        tv=datetime.now()
        if wait_minute:
            time.sleep(60-tv.second)
            tv=datetime.now()
        if self.lminute!=tv.minute:
            self.update_mhistory(tv.minute)
        if self.lhour!=tv.hour:
            self.update_hhistory(tv.hour)
        if self.lday!=tv.day:
            self.update_dhistory(tv.day)

class GMDataSerRead(GMDataHistory):
    def __init__(self, sport, sbaud=9600, twpost=False):
        GMDataHistory.__init__(self)
        self.twpost=twpost
        self.serial=serial.Serial(port=sport, baudrate=sbaud, timeout=30)

    def proc_onechunk(self):
        try:
            data=self.serial.read(1).decode('utf-8')
        except:
            print("error:",sys.exc_info()[0])
            return -1

        if data != "." and data != "0" and data != "1":
            print("received garbage character",)
            print(data)
            return -1
        self.mcount+=1
        udpcon.udpcon_write("pulse %d\n" % self.mcount)
        return 0

    def close(self):
        GMDataHistory.close(self)
        self.serial.close()

STX=b'\x02'
ETX=b'\x03'
ACK=b'\x06'
class GMDataTCSerRead(GMDataHistory):
    def __init__(self, sport, sbaud=115200, twpost=False):
        GMDataHistory.__init__(self)
        self.twpost=twpost
        self.serial=serial.Serial(port=sport, baudrate=sbaud, timeout=1)
        self.send_wait_ack(b'8B0')
        self.send_wait_ack(b'802')

    def send_data(self, data):
        parity=0
        self.serial.write(STX)
        for i in data:
            self.serial.write(i)
            parity^=i
        self.serial.write(ETX)
        ps="%02X" % parity
        for i in ps:
            self.serial.write(i)

    def rec_data_tout(self):
        res=[]
        while True:
            x=self.serial.read()
            if len(x)==0: break
            res.append(x)
        if res[0]!=STX: return NULL
        rss=''
        for i in res[1:]:
            if i==ETX: break
            rss+=i
        parity=0
        for i in rss:
            parity^=i
        if parity!=int(''.join(res[len(res)-2:]), base=16): return None
        return rss

    def send_wait_ack(self, data):
        self.send_data(data)
        x=self.serial.read()
        if len(x)==0: return 1
        if x!=ACK: return -1
        return 0

    def proc_onechunk(self):
        self.send_data('01')
        rd=self.rec_data_tout()
        if rd[0:2]!='01':
            print("received wrong format, %s" % data)
            return -1
        x=int(rd[2:], base=16)
        self.send_data('02')
        self.mcount=0.001 * x
        udpcon.udpcon_write("%5.3f uSv/h\n" % self.mcount)
        return 0

    def close(self):
        GMDataHistory.close(self)
        self.serial.close()

class GMDataRead(GMDataHistory):
    dpcount=0
    def __init__(self, chunk = 1024, dformat = pyaudio.paInt16,
                 channels = 1, rate = 44100,
                 twpost=False, mcount_div=1):
        GMDataHistory.__init__(self)
        self.twpost=twpost
        self.mcount_div=mcount_div
        self.chunk = chunk
        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(format = dformat,
                                   channels = channels,
                                   rate = rate,
                                   input = True,
                                   frames_per_buffer = self.chunk)

    def proc_onechunk(self):
        data = self.stream.read(self.chunk)
        for i in range(0,self.chunk*2,2):
            v=data[i+1]
            if v>=0x80: v=(~v)&0x7f
            if v>thr_upper:
                if debug_print:
                    udpcon.udpcon_write(" +%X" % v)
                if  self.cont==thr_cont_times:
                    self.mcount+=1
                    udpcon.udpcon_write("pulse\n")
                self.cont+=1
                self.discont=0
            elif v<thr_lower:
                if debug_print and self.cont>0:
                    udpcon.udpcon_write(" -%X" % v)
                if self.discont>cont_reset:
                    self.cont=0
                else:
                    self.discont+=1
            else:
                if debug_print and self.cont>0:
                    udpcon.udpcon_write(" |%X" % v)
                self.discont=0

        if debug_print:
           udpcon.udpcon_write(" %X" % v)
           self.dpcount+=1
           if self.dpcount % 16 == 0: udpcon.udpcon_write("\n")

        return 0

    def close(self):
        GMDataHistory.close(self)
        self.stream.close()
        self.pa.terminate()

def usage():
    print("-t|--tweet: Post to Tweeter")
    print("-d|--div2: divide count value by 2(for slbook)")
    print("-p|--debug: print debug messages")
    print("-u value|--upper=value: upper threshold(default=%d)" % thr_upper)
    print("-l value|--lower=value: lower threshold(default=%d)" % thr_lower)
    print("-c value|--creset=value: reset cont parameter(default=%d)" % cont_reset)
    print("-r value|--ctimes=value: cont times threshold(default=%d)" % thr_cont_times)
    print("-s serial_port|--sport=serial_port: set 'arduino' for (/dev/ttyACM0)")
    print("-m machine_mode|--mmode=machine_mode: 'pulse:count pulse|tc TC300S/200S")

class ReadGmdata(Thread):
    def __init__(self, gmdata, wait_minute):
        Thread.__init__(self)
        self.gmdata=gmdata
        self.running=True
        self.wait_minute=wait_minute

    def run(self):
        while self.running:
            self.gmdata.proc_onechunk()
            self.gmdata.data_update(self.wait_minute)


def signal_handler(signal, frame):
    terminate_program=1
    print('got a singal, going to terminate the program')


if __name__ == "__main__":

    try:
        opts, args = getopt.getopt(sys.argv[1:], "tdpc:u:l:r:s:m:",
              ["tweet","div2","debug","creset=","upper=","lower=",
               "ctimes=","sport=","mmode="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    twpost=False
    mcount_div=1
    sport=None
    mmode='pulse'
    wait_minute=False
    for o, a in opts:
        if o in ("-h", "--help"):
           usage()
           sys.exit()
        if o in ("-t", "--tweet"):
           print("Tweeet On")
           twpost=True
        if o in ("-d", "--div2"):
           print("divide count value by 2")
           mcount_div=2
        if o in ("-p", "--debug"):
           debug_print=True
        if o in ("-c", "--creset"):
           cont_reset=int(a)
        if o in ("-u", "--upper"):
           thr_upper=int(a)
        if o in ("-l", "--lower"):
           thr_lower=int(a)
        if o in ("-r", "--ctimes"):
           thr_cont_times=int(a)
        if o in ("-s", "--sport"):
           sport=a
           if sport=="arduino": sport="/dev/ttyACM0"
           print("Use serial port:%s" % sport)
        if o in ("-m", "--mmode"):
           mmode=a

    udpcon=UdpConsole();
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if sport:
        if mmode=='pulse':
            gmdata=GMDataSerRead(sport=sport, twpost=twpost)
        elif mmode=='tc':
            gmdata=GMDataTCSerRead(sport=sport, twpost=twpost)
            wait_minute=True
        else:
            usage()
            sys.exit(2)
    else:
        gmdata=GMDataRead(twpost=twpost, mcount_div=mcount_div)

    read_gmdata=ReadGmdata(gmdata, wait_minute)
    read_gmdata.start()

    while True:
        rs = udpcon.udpcon_read('command(m,h,d,mtweet,dtweet,q)? ')
        if rs.find('q')==0:
            if udpcon.sender:
                udpcon.udpcon_write("can't quit from udp console\n")
                continue
            break
        if rs.find('mtweet')==0:
            tw=TwitterTweet()
            tw.create_msg(gmdata)
            tw.start()
            continue
        if rs.find('dtweet')==0:
            tw=TwitterTweet()
            tw.create_dmsg(gmdata)
            tw.start()
            continue
        if rs.find('m')==0:
            for i in range(len(gmdata.mhistory)):
                udpcon.udpcon_write(" %d" % gmdata.mhistory[i])
            udpcon.udpcon_write("\n")
            continue
        if rs.find('h')==0:
            for i in range(len(gmdata.hhistory)):
                udpcon.udpcon_write(" %d" % gmdata.hhistory[i])
            udpcon.udpcon_write("\n")
            continue
        if rs.find('d')==0:
            for i in range(len(gmdata.dhistory)):
                udpcon.udpcon_write(" %d" % gmdata.dhistory[i])
            udpcon.udpcon_write("\n")
            continue

    read_gmdata.running=False
    read_gmdata.join()
    gmdata.close()
