from deedbundler.otc import Otcdb, GPGManager
import time

if __name__ == '__main__':
	
	otc = Otcdb('/home/mint/dev/github/deedbot/data/db')
	#print otc.update_db()
	otc.open_db()
	trust = otc.assbot_trust()

	gpg = GPGManager('/home/mint/dev/github/deedbot/data/gpg')

	start = time.time()
	print gpg.recv_keys(trust.keys())
	dt = time.time() - start
	print dt/60
