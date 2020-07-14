import argparse
import itertools
import time
import serial

parser = argparse.ArgumentParser()
parser.add_argument('speed', nargs='*', default=['1', '2', '3', '2', '1', '0'])
parser.add_argument('--port', default='COM5')
parser.add_argument('--pause', type=float, default=2)

args = parser.parse_args()
port = args.port

try:
	speeds = [int(s.strip()) for s in args.speed if s.strip()]
except:
	raise parser.error('speeds must be single characters')

with serial.Serial(port, 57600, timeout=1.) as port:
	for speed in itertools.cycle(speeds):
		port.write(b'%d' % speed)
		port.flush()
		print(port.readline().decode().strip())
		time.sleep(args.pause)

