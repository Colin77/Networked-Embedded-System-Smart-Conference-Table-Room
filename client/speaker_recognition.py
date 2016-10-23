#!/usr/bin/env python
from __future__ import print_function
import subprocess
import sys
from threading import Thread
from Queue import Queue, Empty
import os
import struct

CMD_MFCC = '/usr/local/bin/x2x +sf | /usr/local/bin/frame | /usr/local/bin/mfcc'
CMD_ENROLL = '/usr/local/bin/gmm -l 12'
CMD_PREDICT = '/usr/local/bin/gmmp -a -l 12 %s'
DIR_GMM = '/home/root/speakerdata/'

INPUT_BUF_SIZE = 16 * 1000 * 16 / 8 # 16kHz 16 bit
MFCC_BUF_SIZE = 32

def main():
    if len(sys.argv) < 3 or ( sys.argv[1] != 'enroll' and sys.argv[1] != 'predict' ):
        print('Usage: ' + sys.argv[0] + ' enroll|predict file.raw')
        sys.exit(0)
    if sys.argv[1] == 'enroll':
        process_enroll()
    if sys.argv[1] == 'predict':
        process_predict()

def process_enroll():
    name = raw_input('Name: ')
    gmm_result_queue = Queue()
    with open(sys.argv[2], 'rb') as f:
        buf = bytearray(INPUT_BUF_SIZE)
        p = subprocess.Popen([CMD_MFCC], shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        p_gmm = subprocess.Popen(CMD_ENROLL.split(), stdin=p.stdout, stdout=subprocess.PIPE)
        gmm_thread = Thread(target=get_gmm_result, args=[p_gmm.stdout, gmm_result_queue])
        gmm_thread.start()
        while True:
            n = f.readinto(buf)
            if n == 0:
                break
            if n < len(buf):
                p.stdin.write(buf[:n])
                break
            p.stdin.write(buf)
        p.stdin.close()
        p.wait()
        p_gmm.wait()
    gmm_data = gmm_result_queue.get()
    with open(DIR_GMM + name + '.gmm', 'wb') as gmm_file:
        gmm_file.write(gmm_data)

def process_predict():
    mfcc_result_queue = Queue()
    with open(sys.argv[2], 'rb') as f:
        buf = bytearray(INPUT_BUF_SIZE)
        while True:
            n = f.readinto(buf)
            if n == 0:
                break
            p = subprocess.Popen([CMD_MFCC], shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            mfcc_thread = Thread(target=get_mfcc_result, args=[p.stdout, mfcc_result_queue])
            mfcc_thread.start()
            if n < len(buf):
                p.stdin.write(buf[:n])
            else:
                p.stdin.write(buf)
            p.stdin.close()
            p.wait()
            mfcc_data = mfcc_result_queue.get()
            find_best_gmm_match(mfcc_data)
#  i = 0
#  for c in mfcc_data:
#    print('%d:%s' % (i, hex(ord(c))))
#    i = i + 1
def find_best_gmm_match(mfcc_data):
    gmm_result_queue = Queue()
    for filename in os.listdir(DIR_GMM):
        if not filename.endswith('.gmm'):
            continue
        path = os.path.join(DIR_GMM, filename)
        p_gmm = subprocess.Popen((CMD_PREDICT % path).split(),  stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        gmm_thread = Thread(target=get_gmm_result, args=[p_gmm.stdout, gmm_result_queue])
        gmm_thread.start()
        p_gmm.stdin.write(mfcc_data)
        p_gmm.stdin.close()
        p_gmm.wait()
        result = gmm_result_queue.get()
        print(filename)
        ave_logp = struct.unpack('f', result)[0]
        print(ave_logp)

def get_mfcc_result(out,result_queue):
    buf = out.read()
    result_queue.put(buf)

def get_gmm_result(out,result_queue):
    buf = out.read()
    result_queue.put(buf)

if __name__ == '__main__':
    main()
