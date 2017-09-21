import socket, time

FICTRAC_HOME = 'D:/Dropbox/princeton/fly_vr/FicTrac/FicTrac/'
HOST = 'localhost'

# Get the local port the FicTrac server is running on.
with(open(FICTRAC_HOME + 'socket.port')) as f:
    PORT = int(f.readline())

tstart = time.time()
loop_cnt = 1
loop_av = 0
oldFrameNo = -1
while 1:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
    reply = sock.recv(128)
    line = reply.decode('UTF-8')

    ##  strip data vals
    toks = line.split()
    FrameNo = int(toks[0])
    PosX = float(toks[1])
    PosY = float(toks[2])
    VelX = float(toks[3])
    VelY = float(toks[4])
    Theta = float(toks[5])

    if(oldFrameNo == FrameNo):
        time.sleep(0.01)
        continue

    if( oldFrameNo != -1 and (FrameNo - oldFrameNo) > 1):
        print("Missed {} frames! new FrameNo={}".format(FrameNo - oldFrameNo - 1, FrameNo))


    oldFrameNo = FrameNo

    tnow = time.time()
    loop_av += 0.001 * ((tnow - tstart) * 1000 - loop_av)

    print(loop_cnt, FrameNo, PosX, PosY, VelX, VelY, Theta, loop_av)

    loop_cnt += 1
    tstart = tnow

    time.sleep(.01)

# def follow_socket():
#     tstart = time.time()
#     loop_cnt = 1
#     loop_av = 0
#     HOST = 'localhost'
#     oldFrameNo = -1
#
#     while True:
#         sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         sock.connect((HOST, PORT))
#         reply = sock.recv(128)
#         line = reply.decode('UTF-8')
#         sock.shutdown(socket.SHUT_RD)
#         sock.close()
#
#         ##  strip data vals
#         toks = line.split()
#         FrameNo = int(toks[0])
#
#         if(FrameNo == oldFrameNo):
#             time.sleep(0.01)
#             continue
#
#         oldFrameNo = FrameNo
#
#         PosX = float(toks[1])
#         PosY = float(toks[2])
#         VelX = float(toks[3])
#         VelY = float(toks[4])
#         Theta = float(toks[5])
#
#         tnow = time.time()
#         loop_av += 0.001 * ((tnow - tstart) * 1000 - loop_av)
#
#         loop_cnt += 1
#         tstart = tnow
#
#         time.sleep(0.01)
#
#         yield (FrameNo, PosX, PosY, VelX, VelY, Theta, loop_av, loop_cnt-1)
#
# def follow_file(thefile):
#     thefile.seek(0,2)
#     while True:
#         line = thefile.readline()
#         if not line:
#             time.sleep(0.1)
#             continue
#         yield line
#
# if __name__ == '__main__':
#
#     while(1):
#         try:
#             #logfile = open(FICTRAC_HOME+'170425_103.dat',"r")
#
#             # Get the local port the FicTrac server is running on.
#             with(open(FICTRAC_HOME + 'socket.port')) as f:
#                 PORT = int(f.readline())
#
#             sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#             sock.connect(('localhost', PORT))
#
#             loglines = follow_socket()
#
#             #loglines = follow_file(logfile)
#             for line in loglines:
#                 print line
#                 print "\n"
#
#             break
#         except IOError, socket.error:
#             continue