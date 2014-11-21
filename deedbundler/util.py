# -*- coding: utf-8 -*-
import re
import time
from urlparse import urlparse

import requests


def raw_pastebin(url):
	p = urlparse(url)
	if p.netloc == 'dpaste.com' and not p.path.endswith('.txt'):
		url = '{0}.txt'.format(url)
	elif p.netloc == 'pastebin.com' and 'raw.php' not in p.path:
		url = 'http://pastebin.com/raw.php?i={0}'.format(p.path[1:])
	elif p.netloc == 'pastebin.ca' and '/raw/' not in p.path:
		url = 'http://pastebin.ca/raw/{0}'.format(p.path[1:])
	elif p.netloc == 'fpaste.org' and '/raw' not in p.path:
		match = re.search('fpaste\.org/([0-9]+)', url)
		if match:
			url = 'http://fpaste.org/{0}/raw/'.format(match.group(1))
	return url


def fetch_url(url, limit=None, timeout=None, proxy=None):
	r = requests.get(url)
	content = ''
	return content


## GPG message extraction

sig_patterns = r'(-----BEGIN PGP SIGNED MESSAGE-----.+?(?<!- )-----END PGP SIGNATURE-----|-----BEGIN PGP MESSAGE-----.+?(?<!- )-----END PGP MESSAGE-----)'
sig_rx = re.compile(sig_patterns, re.DOTALL)

def extract_gpg_msg(text):
	deeds = sig_rx.findall(text)
	return deeds


content_rx = re.compile(r'-----BEGIN PGP SIGNED MESSAGE-----.+?\n\n(.+?)(?<!- )-----BEGIN PGP SIGNATURE-----', re.DOTALL)

def gpg_content(text):
	text = text.replace('\r\n', '\n').replace('\r', '\n')
	match = content_rx.search(text)
	if not match:
		return None
	content = match.group(1)
	return content


title_rx = re.compile('(?:DEED_TITLE|TITLE):\s*(.+)', re.IGNORECASE)

def deed_title(text, length=80):
	
	match = title_rx.search(text)
	if match:
		title = match.group(1).strip().strip('\'"')
	else:
		content = gpg_content(text)
		if not content:
			return None
		title = ''
		for line in content.split('\n'):
			title += line.lstrip()
			if len(title) > 8:
				break
			else:
				title += ' '

	return title[:length] if title else None



## Base58

__b58chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
__b58base = len(__b58chars)

def b58encode(v):
	""" encode v, which is a string of bytes, to base58."""
	long_value = 0L
	for (i, c) in enumerate(v[::-1]):
		long_value += (256**i) * ord(c)

	result = ''
	while long_value >= __b58base:
		div, mod = divmod(long_value, __b58base)
		result = __b58chars[mod] + result
		long_value = div
	result = __b58chars[long_value] + result

	# Bitcoin does a little leading-zero-compression:
	# leading 0-bytes in the input become leading-1s
	nPad = 0
	for c in v:
		if c == '\0': nPad += 1
		else: break

	return (__b58chars[0]*nPad) + result

def b58decode(v, length):
	""" decode v into a string of len bytes."""
	long_value = 0L
	for (i, c) in enumerate(v[::-1]):
		long_value += __b58chars.find(c) * (__b58base**i)

	result = ''
	while long_value >= 256:
		div, mod = divmod(long_value, 256)
		result = chr(mod) + result
		long_value = div
	result = chr(long_value) + result

	nPad = 0
	for c in v:
		if c == __b58chars[0]: nPad += 1
		else: break
	result = chr(0)*nPad + result

	if length is not None and len(result) != length:
		return None

	return result


## Electrum helpers

def electrum_start(config, start_daemon=True):
	from electrum import NetworkProxy, Wallet, WalletStorage, SimpleConfig
	from electrum.daemon import get_daemon

	_config = SimpleConfig(config)
	daemon_socket = get_daemon(_config, start_daemon=start_daemon)
	network = NetworkProxy(daemon_socket, _config)
	network.start()

	# wait until connected
	while network.is_connecting():
		time.sleep(0.1)
	if not network.is_connected():
		sys.exit('electrum daemon is not connected')

	storage = WalletStorage(_config)
	if storage.file_exists:
		wallet = Wallet(storage)
	else: 
		sys.exit('wallet file is missing')

	#self.wallet.synchronize = lambda: None
	wallet.start_threads(network)

	# wait for wallet to update
	wallet.update()

	return (network, wallet)

def electrum_stop(network, wallet):
	wallet.stop_threads()
	network.stop()

