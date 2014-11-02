# -*- coding: utf-8 -*-
import sys
import base64
import json
import hashlib
from datetime import datetime

import requests
import gnupg

from coinkit import BitcoinPrivateKey


DEED_SOURCE = '1LAwrWMbPLLSpt7nkD5Jv1Yf4cwPhD98ny'

def verify_raw_bundle(path, gpgverify=False):
	with open(path, 'r') as f:
		raw = f.read()

	deeds = extract_gpg(raw)
	if not deeds:
		print 'Error: No deeds found in bundle'
		return
	b58_hashes = []
	for i,deed in enumerate(deeds,1):
		dh = hashlib.sha256(deed)
		sha256 = dh.hexdigest()
		b58 = b58encode(dh.digest())
		b58_hashes.append(b58)
		print 'Deed {0}: {1}'.format(i, b58)

	
	lite_bundle = ','.join(b58_hashes)
	bh = hashlib.sha256(lite_bundle)
	bundle_hash = bh.hexdigest()

	k = BitcoinPrivateKey(bundle_hash)
	address = k.public_key().address()
	wif = k.to_wif()

	status = address_tx(address)

	print 'Lite bundle: ' + lite_bundle
	print 'Bundle sha256: ' + bundle_hash
	print 'Bundle address: ' + address
	print 'WIF: ' + wif
  	if status:
		txid, timestamp, block = status
		date = datetime.fromtimestamp(int(timestamp)).strftime('%Y/%m/%d %H:%M:%S')
		print 'Status: confirmed'
		print ' txid: ' + txid
		print ' sent: ' + date
		print ' block: {0}'.format(block)

	else:
		print 'Status: unconfirmed'     


def hash_deed(deed):
	pass

def address_tx(address, conf=0):
	url = 'https://blockchain.info/address/{0}?format=json'.format(address)
	r = requests.get(url)
	js = r.json()
	if not js or 'txs' not in js:
		return False

	for tx in js['txs']:
		for inp in tx['inputs']:
			if inp['prev_out']['addr'] == DEED_SOURCE:
				txid = tx['hash']
				timestamp = tx['time']
				block = tx['block_height'] if 'block_height' in tx else 0
				return (txid, timestamp, block)
	return False

## GPG message extraction

sig_patterns = [
	'-----BEGIN PGP SIGNED MESSAGE-----.+?-----END PGP SIGNATURE-----',
	'-----BEGIN PGP MESSAGE-----.+?-----END PGP MESSAGE-----'
	]
sig_rx = re.compile('({0})'.format('|'.join(sig_patterns)), re.DOTALL)

def extract_gpg(text):
	deeds = sig_rx.findall(text)
	return deeds

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


if __name__ == '__main__':

	path = sys.argv[1]

	if '.rbundle' in path:
		verify_raw_bundle(path)
		sys.exit()

