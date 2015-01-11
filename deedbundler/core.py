# -*- coding: utf-8 -*-
import os
import sys
import re
import time
import hashlib
import zlib
import json
import sqlite3
from decimal import Decimal
from collections import defaultdict
from Queue import Queue
from threading import Thread

import requests
import gnupg

from electrum import NetworkProxy, Wallet, WalletStorage, SimpleConfig, Transaction
from electrum.daemon import get_daemon

from .packages.coinkit import BitcoinPrivateKey
from .db import BundlerDB
from .otc import OTCDB, GPGManager
from .util import raw_pastebin, extract_gpg_msg, deed_title, electrum_start, electrum_stop, b58encode, b58decode


class Bundler(object):

	def __init__(self, config, send_txs=True, update_trust=True):
		self.db = None
		self.config = config
		self.trusted = {}

		# don't broadcast tx if dry run
		self.send_txs = send_txs
		self.update_trust = update_trust

		self.hooks = {
			'deed': [],
			'bundle': [],
			'bundle_update': [],
			'trust_update': [],
			}


	def setup(self):
		# connect to databases
		dbpath = '{0}/{1}'.format(self.config['db_path'], self.config['db_name'])
		self.db = BundlerDB(dbpath)
		self.db.open_db()

		self.otcdb = OTCDB(self.config['db_path'])
		self.otcdb.open_db()
		self.trusted = self.otcdb.assbot_trust()
		self.otcdb.close_db()

		self.gpg = GPGManager(self.config['gpg_path'])


		# start electrum
		self.network, self.wallet = electrum_start(self.config['electrum_config'])

		# start threads
		self.tx_queue = Queue()
		if not self.send_txs:
			tx_sender = Thread(target=self.tx_sender)
			tx_sender.daemon = True
			tx_sender.start()

		self.trust_changes = Queue()
		if self.update_trust:
			trust_updater = Thread(target=self.trust_updater)
			trust_updater.daemon = True
			trust_updater.start()

		self.hook_queue = Queue()
		hook_runner = Thread(target=self.hook_runner)
		hook_runner.daemon = True
		hook_runner.start()

	def shutdown(self):
		electrum_stop(self.network, self.wallet)
		self.db.close_db()
		time.sleep(1)


	def hook_runner(self):
		print 'hook_runner thread started'
		while True:
			hook, data = self.hook_queue.get()
			for fn in self.hooks[hook]:
				try:
					fn(data)
				except Exception as e:
					print 'hookrunner: exception {0}'.format(e)


	def tx_sender(self):
		print 'tx_sender thread started'
		while True:
			tx = self.tx_queue.get()
			try:
				result = self.send_tx(tx)

				if not result[0]:
					print 'tx_sender: fail {0}'.format(result[1])
					#time.sleep(10)
					#self.tx_queue.put(tx)
				else:
					txid = tx.hash()
					print 'tx_sender: sent {0}'.format(txid)

			except Exception as e:
				print 'txsender: exception {0}'.format(e)


	def trust_updater(self):
		print 'trust_updater thread started'
		while True:
			time.sleep(self.config['update_trust_interval'])
			try:
				new_trust = self.otcdb.update_trust()
				added, removed = self.otcdb.trust_diff(self.trusted, new_trust)
				self.trusted = new_trust

				tu = {'trusted': self.trusted, 'timestamp': int(time.time())}
				self.hook_queue.put(('trust_update', tu))

				if added:
					self.gpg.recv_keys(added)
				#if removed:
				#	self.gpg.delete_keys([r[0] for r in removed])
				
				# just the nicknames
				changed = (
					[self.trusted[nk][0] for nk in new_keys],
					[rk[1] for rk in removed],
					)
				self.trust_changes.put(changed)
				print 'trust_updater: {0} added {1} removed'.format(len(new_keys), len(removed))


			except Exception as e:
				print 'trust_updater: {0}'.format(e)


	def should_bundle(self):
		now = int(time.time())

		# not enough money left
		if self.num_bundles_left() < 1:
			return (False, 'no_money')

		pend = self.db.pending_count()
		pending_num = pend[0]
		oldest_deed = pend[1]
		# no pending deeds
		if pending_num < 1:
			return (False, 'no_deeds')
		# wait for oldest deed to be at least X seconds old
		if oldest_deed and (now - oldest_deed) < self.config['min_oldest_deed']:
			return (False, 'too_fresh')

		last_bundle = self.db.last_bundle()
		# this is the first bundle ever, go ahead
		if not last_bundle:
			return (True, 'ok')
		# too soon
		time_elapsed = now - last_bundle['created_at']
		if time_elapsed < self.config['min_bundle_interval']:
			return (False, 'too_soon')

		# stop bundling if previous bundles remain unconfirmed
		unconf = self.db.unconfirmed_bundles()
		max_unconfirmed = self.config['max_unconfirmed_bundles']
		if unconf > max_unconfirmed:
			return (False, 'no_conf')

		return (True, 'ok')


	def make_bundle(self):
		status, msg = self.should_bundle()
		if not status:
                    return (False, msg)

		# find pending deeds
		max_deeds = self.config['deeds_per_bundle']
		pending_deeds = self.db.pending_deeds(max_deeds)
		deed_hashes = [(row['b58_hash'], row['id']) for row in pending_deeds]

		deed_count = len(deed_hashes)
		if not deed_count > 0:
			return (False, 'no_deeds?')
		
		bundled_at = int(time.time())
		# create the bundle hash
		lite_bundle = ','.join([dh[0] for dh in deed_hashes])
		bh = hashlib.sha256(lite_bundle)
		bundle_hash = bh.hexdigest()
		bundle_int = int(bundle_hash, 16)

		# hash must be smaller than curve order
		secp256_order = 0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141
		if not (0 < bundle_int < secp256_order):
			# we can't make a key with this bundle hash
			# wait for new deeds
			return (False, 'outside_curve_order')

		# check if bundle_hash exists
		if self.db.bundle_exists(bundle_hash):
			return (False, 'dupe_bundle')

		# create address
		# make transaction to address
		try:
			address, wif = self.make_address(bundle_hash)	
			tx = self.make_tx(address)
			txid = tx.hash()
		except:
			raise
			return (False, 'mktx_fail')

		# mark deeds as bundled
		# save the bundle
		deed_ids = [dh[1] for dh in deed_hashes]
		bundle = {
			'lite_bundle': lite_bundle,
			'num_deeds': deed_count,
			'sha256_hash': bundle_hash,
			'wif': wif,
			'address': address,
			'txid': txid,
			'created_at': bundled_at,
			'sendtx_at': int(time.time()),
			}
		self.db.save_bundle(bundle, deed_ids)

		self.hook_queue.put(('bundle', bundle))	

		# send the transaction
		if not self.dry_run:
			self.tx_queue.put(tx)

		return (True, (deed_count, address))

	
	def confirm_bundle(self):
		bundle = self.db.last_unconfirmed_bundle()
		if not bundle:
			return (False, 'no_unconfirmed')

		bundle_id = bundle['id']
		address = bundle['address']
		txid = bundle['txid']
		now = int(time.time())
		since_creation = now - bundle['created_at']

		# check electrum's tx verifier directly
		conf, timestamp = self.wallet.verifier.get_confirmations(txid)

		if conf > 0 and conf >= self.config['tx_confirm']:
			ts = int(timestamp)
			self.db.confirm_bundle(bundle_id, ts)

			up = {'confirmed_at': ts, 'txid': txid, 'address': address}
			self.hook_queue.put(('bundle_update', up))

			return (True, (address, bundle['num_deeds'], txid))

		since_sendtx = now - bundle['sendtx_at']
		if since_creation > self.config['resend_tx_after'] and since_sendtx > self.config['sendtx_retry_between']:
			# has the wallet even heard of this txid?
			with self.wallet.transaction_lock:
				if txid in self.wallet.transactions:
					# guess we are waiting for a slow block
					return (False, 'waiting_for_confirm')
				else:
					# wallet doesn't know about txid, maybe we should make a new tx
					try:
						new_tx = self.make_tx(address)
						new_txid = new_tx.hash()
					except Exception as e:
						return (False, 'retry_mktx_fail')
			
					self.db.update_txid(bundle_id, new_txid, int(time.time()))

					up = {'confirmed_at': None, 'txid': txid, 'address': address}
					self.hook_queue.put(('bundle_update', up))

					if not self.dry_run:
						self.tx_queue.put(new_tx)

					return (False, 'retried_tx')
		else:
			return (False, 'waiting_for_confirm')


	def status(self):
		pending, oldest = self.db.pending_count()

		row = self.db.last_bundle()
		last_bundle = row['created_at'] if row else 0

		unconfirmed = self.db.unconfirmed_count()

		return (pending, last_bundle, unconfirmed)


	def save_deeds(self, content):
		deeds, errors = self.extract_deeds(content)
		self.db.save_deeds(deeds)

		for deed in deeds:
			self.hook_queue.put(('deed',deed))

		d = [(i['otc_name'],i['b58_hash'],i['title']) for i in deeds]
		return (d, errors)		


	def extract_deeds(self, content):
		good_deeds = []
		errors = []
		# extract signed messages
		deeds = extract_gpg_msg(content)
		if not deeds:
			return (good_deeds, errors)

		for i,deed in enumerate(deeds,1):
			status, data = self.parse_deed(deed)
			if status:
				good_deeds.append(data)
			else:
				errors.append((i, data))
		return (good_deeds, errors)


	def parse_deed(self, deed):
		# skip if deed is too big
		if len(deed) > self.config['max_deed_size']:
			return (False, 'too_big')

		timestamp = int(time.time())
		# hash deed
		dh = hashlib.sha256(deed)
		deed_hash = dh.hexdigest()
		# encode hash
		b58_hash = b58encode(dh.digest())

		# skip if deed already exists
		if self.db.deed_exists(b58_hash):
			return (False, 'dupe')

		# make sure signature is valid and trusted
		result = self.gpg.verify(deed)
		if result.valid:
			# check if trusted
			if result.fingerprint in self.trusted:
				fingerprint = result.fingerprint
			elif result.pubkey_fingerprint in self.trusted:
				fingerprint = result.pubkey_fingerprint
			else:
				return (False, 'untrusted')

			# parse deed title
			title = deed_title(deed, self.config['deed_title_length'])
			otc_name = self.trusted[fingerprint][0]
			#deed_data = (fingerprint, otc_name, deed_hash, b58_hash, deed, title)
			deed_data = {
				'fingerprint': fingerprint,
				'otc_name': otc_name,
				'sha256_hash': deed_hash,
				'b58_hash': b58_hash,
				'raw': deed,
				'title': title,
				'created_at': timestamp,
				}
			return (True, deed_data)
		else:
			if results.status == 'no public key':
				return (False, 'no_pubkey')
			else:
				return (False, 'invalid')

	# just for testing
	def find_deeds(self, url):
		url = raw_pastebin(url)
		r = requests.get(url)
		return self.save_deeds(r.content)


	def make_address(self, bundle_hash):
		k = BitcoinPrivateKey(bundle_hash)
		address = k.public_key().address()
		wif = k.to_wif()
		return (address, wif)


	def make_tx(self, address):
		# update wallet so we have the latest inputs
		#self.wallet.update()
		# make tx
		outputs = [('address', address, self.config['tx_amount'])]
		password = self.config['wallet_pass']
		fee = self.config['tx_fee']
		change_addr = self.config['main_address']
		tx = self.wallet.mktx(outputs, password, fee, change_addr)	
		return tx


	def make_custom_tx(self, address, amount):
		# update wallet so we have the latest inputs
		#self.wallet.update()
		# make tx
		outputs = [('address', address, amount)]
		password = self.config['wallet_pwd']
		fee = self.config['tx_fee']
		change_addr = self.config['main_address']
		tx = self.wallet.mktx(outputs, password, fee, change_addr)	
		return tx


	def send_tx(self, tx):
		h = self.wallet.send_tx(tx)
		timeout = self.config['sendtx_timeout']
		if not self.wallet.tx_event.wait(timeout):
			return (False, 'timeout')
		return self.wallet.receive_tx(h, tx)


	def num_bundles_left(self):
		confirmed, unconfirmed = self.main_balance()
		per_bundle = self.config['tx_amount'] + self.config['tx_fee']
		num = int(confirmed / per_bundle)
		return num


	def main_balance(self):
		return self.wallet.get_addr_balance(self.config['main_address'])


	def addr_balance(self, addr):
		out = self.network.synchronous_get([ ('blockchain.address.get_balance',[addr]) ])[0]
		out["confirmed"] = str(Decimal(out["confirmed"])/100000000)
		out["unconfirmed"] = str(Decimal(out["unconfirmed"])/100000000)
		return out


