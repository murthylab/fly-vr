import time
import logging
logging.basicConfig(level=logging.DEBUG)


from flyvr.hwio.phidget import PhidgetIO


def get_phidget():
	return PhidgetIO(tp_start=3, tp_stop=4, tp_next=5, tp_enable=True)


# pulse = rising edge, delay, falling edge


def test_1(high_time):
	# sends
	# 1. start (pulse high)
	# 2. acquires 3 stacks (each stack 3s long, i.e. ~24 frames)
	#    * pulses next_image high only
	# 3. pulses stop high

	p = get_phidget()

	print("testing pulse next only, high_time=", high_time)

	# start
	p._pulse(p._tp_start, high_time=high_time)

	# wait 5s for warmup
	print('sent start waiting 5s (stack 0 = warmup)')
	time.sleep(5)


	# take ~25 frames per stack (~3s @ 8fps), take 3 stacks
	for stack in range(3):
		print("stack ", stack+1)  # add one because we already started one with the start of acqusition

		# pulse *only* next high
		p._pulse(p._tp_next, high_time=0.001)

		time.sleep(3.)

	print('sending stop')
	p._pulse(p._tp_stop, high_time=0.001)

	time.sleep(0.5)
	print('closing')
	p.close()


def test_2(high_time):
	# sends
	# 1. start (pulse high)
	# 2. acquires 3 stacks (each stack 3s long, i.e. ~24 frames)
	#    * pulses next_image high
	#    * pulses start high
	# 3. pulses stop high

	p = get_phidget()

	print("testing pulse next and then pulse start, high_time=", high_time)

	# start
	p._pulse(p._tp_start, high_time=high_time)

	# wait 5s for warmup
	print('sent start waiting 5s (stack 0 = warmup)')
	time.sleep(5)


	# take ~25 frames per stack (~3s @ 8fps), take 3 stacks
	for stack in range(3):
		print("stack ", stack+1)  # add one because we already started one with the start of acqusition

		# pulse next high
		p._pulse(p._tp_next, high_time=high_time)
		# wait also between the pulses, although this is debatable if necessary, and how long for
		time.sleep(0.15)
		# pulse start high
		p._pulse(p._tp_start, high_time=high_time)

		time.sleep(3.)

	print('sending stop')
	p._pulse(p._tp_stop, high_time=high_time)

	time.sleep(0.5)
	print('closing')
	p.close()


def test_3(high_time):
	# sends
	# 1. start (pulse high)
	# 2. acquires 3 stacks (each stack 3s long, i.e. ~24 frames)
	#    * rising edge next
	#    * rising edge start
	#    * delay
	#    * falling edge start
	#    * falling edge next
	# 3. pulses stop high

	p = get_phidget()

	print("testing simultaenous pulse next and start, high_time=", high_time)

	# start
	p._pulse(p._tp_start, high_time=high_time)

	# wait 5s for warmup
	print('sent start waiting 5s (stack 0 = warmup)')
	time.sleep(5)


	# take ~25 frames per stack (~3s @ 8fps), take 3 stacks
	for stack in range(3):
		print("stack ", stack+1)  # add one because we already started one with the start of acqusition

		p._tp_next.setDutyCycle(1)
		p._tp_start.setDutyCycle(1)

		time.sleep(high_time)

		p._tp_start.setDutyCycle(0)
		p._tp_next.setDutyCycle(0)

		time.sleep(3.)

	print('sending stop')
	p._pulse(p._tp_stop, high_time=high_time)

	time.sleep(0.5)
	print('closing')
	p.close()





if __name__ == "__main__":
	#test_1(high_time=0.1)
	test_2(high_time=0.1)
	#test_3(high_time=0.1)
