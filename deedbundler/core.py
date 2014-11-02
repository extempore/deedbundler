# -*- coding: utf-8 -*-
import os
import sys
import re
import time
import hashlib
import zlib
import sqlite3
from decimal import Decimal
from collections import defaultdict
from Queue import Queue
from threading import Thread

import requests
import gnupg

from electrum import NetworkProxy, Wallet, WalletStorage, SimpleConfig
from electrum.daemon import get_daemon
from electrum.bitcoin import b58encode, b58decode

from .packages.coinkit import BitcoinPrivateKey
from .otc import Otcdb, GPGManager
from .util import raw_pastebin, extract_gpg, deed_title, electrum_start, electrum_stop


class Bundler(object):

	def __init__(self, config, dry_run=False, update_trust=True):
		self.db = None
		self.config = config
		# don't broadcast tx if dry run
		self.dry_run = dry_run
		# spawn trust updater
		self.update_trust = update_trust
		self.trusted = {}

	def setup(self):
		self.open_db()
		self.otcdb = Otcdb(self.config['db_path'])
		self.load_assbot_trust()
		self.gpg = GPGManager(self.config['gpg_path'])
		# start electrum
		self.network, self.wallet = electrum_start(self.config['electrum_config'])
		# start threads
		self.tx_queue = Queue()
		if not self.dry_run:
			tx_sender = Thread(target=self.tx_sender)
			tx_sender.daemon = True
			tx_sender.start()
		if self.update_trust:
			trust_updater = Thread(target=self.trust_updater)
			trust_updater.daemon = True
			trust_updater.start()

	def shutdown(self):
		electrum_stop(self.network, self.wallet)
		self.db.close()
		time.sleep(1)

	def tx_sender(self):
		print 'tx_sender thread started'
		while True:
			tx = self.tx_queue.get()
			result = self.wallet.sendtx(tx)
			if not result[0]:
				# sendtx failed, sleep and re-queue
				print 'tx_sender: sendtx failed'
				time.sleep(1)
				self.tx_queue.put(tx)
			else:
				print 'tx_sender: {0}'.format(tx.hash())

	def trust_updater(self):
		print 'trust_updater thread started'
		while True:
			time.sleep(self.config['update_trust_interval'])
			try:
				self.otcdb.update_db()
				new_keys = self.load_assbot_trust()
				if new_keys:
					self.gpg.recv_keys(new_keys)
				print 'trust_updater: {0} new keys'.format(len(new_keys))
			except:
				pass

	def load_assbot_trust(self):
		self.otcdb.open_db()
		trusted = self.otcdb.assbot_trust()
		self.otcdb.close_db()
		new_keys = []
		if self.trusted:
			new_keys = list(set(trusted.keys()) - set(self.trusted.keys()))
		self.trusted = trusted
		return new_keys

	def _commit(self):
		'''a commit wrapper to give it another few tries if it errors.
		which sometimes happens due to OperationalError: database is locked'''
		for i in xrange(15):
			try:
				self.db.commit()
			except:
				time.sleep(1)

	def open_db(self):
		filename = '{0}/{1}'.format(self.config['db_path'], self.config['db_name'])

		if os.path.exists(filename):
			self.db = sqlite3.connect(filename, timeout=15, check_same_thread = False)
			self.db.row_factory = sqlite3.Row
			#db.text_factory = str
			return

		self.db = sqlite3.connect(filename, timeout=15, check_same_thread = False)
		self.db.row_factory = sqlite3.Row
		cursor = self.db.cursor()
		cursor.execute("""CREATE TABLE deeds (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				fingerprint TEXT NOT NULL,
				otc_name TEXT NOT NULL,
				deed_hash TEXT NOT NULL,
				b58_hash TEXT NOT NULL,
				deed BLOB NOT NULL,
				title TEXT,
				created_at INTEGER NOT NULL,
				bundled_at INTEGER,
				bundle_address TEXT)
				""")

		cursor.execute("""CREATE TABLE bundles (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				deed_hashes TEXT NOT NULL,
				num_deeds INTEGER NOT NULL,
				bundle_hash TEXT NOT NULL,
				wif TEXT NOT NULL,
				address TEXT NOT NULL,
				txid TEXT,
				created_at INTEGER NOT NULL,
				confirmed_at INTEGER)
				""")
		cursor.execute('CREATE INDEX d_b58 ON deeds (b58_hash)')
		cursor.execute('CREATE INDEX d_address ON deeds (bundle_address)')
		cursor.execute('CREATE INDEX b_address ON bundles (address)')
		self._commit()

	def queue_deeds(self, deeds):
		if not deeds:
			return
		cursor = self.db.cursor()
		insert = 'INSERT INTO deeds VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
		timestamp = int(time.time())

		for deed in deeds:
			(fingerprint, otc_name, deed_hash, b58_hash, deed_text, title) = deed
			# compress deed text before storing, need to uncompress when reading
			deed_blob = sqlite3.Binary(zlib.compress(deed_text))
			row = (fingerprint, otc_name, deed_hash, b58_hash, deed_blob, title, timestamp, 0, None)
			cursor.execute(insert, row)
		self._commit()


	def should_bundle(self):
		cursor = self.db.cursor()
		now = int(time.time())

		# not enough money left
		if self.num_bundles_left() < 1:
			return (False, 'no_money')

		check_deeds = 'SELECT count(id), min(created_at) FROM deeds WHERE bundled_at = 0'
		row = cursor.execute(check_deeds).fetchone()
		oldest_deed = row[1]

		# no pending deeds
		if row and row[0] < 1:
			return (False, 'no_deeds')

		check_bundles = 'SELECT created_at FROM bundles ORDER BY created_at DESC LIMIT 1'
		row = cursor.execute(check_bundles).fetchone()

		# this is the first bundle ever, go ahead
		if not row:
			return (True, 'ok')

		# too soon
		time_elapsed = now - row['created_at']
		if time_elapsed < self.config['min_bundle_interval']:
			return (False, 'too_soon')

		if (now - oldest_deed) < self.config['min_oldest_deed']:
			return (False, 'too_soon.')

		# stop bundling if previous bundles remain unconfirmed
		unconf = 'SELECT count(id) FROM bundles WHERE confirmed_at = 0'
		row = cursor.execute(unconf).fetchone()
		max_unconfirmed = self.config['max_unconfirmed_bundles']
		if row and row[0] > max_unconfirmed:
			return (False, 'no_conf')

		return (True, 'ok')

	def make_bundle(self):
		status, msg = self.should_bundle()
		if not status:
                    return (False, msg)

		cursor = self.db.cursor()

		# find pending deeds
		max_deeds = self.config['deeds_per_bundle']
		sel = 'SELECT * FROM deeds WHERE bundled_at = 0 ORDER BY created_at ASC LIMIT {0}'.format(max_deeds)
		results = cursor.execute(sel)

		temp_path = '{0}/temp_bundle'.format(self.config['bundle_path'])
		temp_file = open(temp_path, 'wb')

		deed_hashes = []
		for row in results:
			deed_hashes.append((row['b58_hash'], row['id']))
			# append deed to temp bundle
			deed = zlib.decompress(row['deed'])
			temp_file.write(deed)
			temp_file.write('\n\n')
		temp_file.close()

		deed_count = len(deed_hashes)
		if not deed_count > 0:
			return (False, 'no_deeds?')
		
		bundled_at = int(time.time())
		# create the bundle hash
		all_hashes = ','.join([dh[0] for dh in deed_hashes])
		bh = hashlib.sha256(all_hashes)
		bundle_hash = bh.hexdigest()
		bundle_int = int(bundle_hash, 16)

		# hash must be smaller than curve order
		secp256_order = 0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141
		if not (1 <= bundle_int < secp256_order):
			# we can't make a key with this bundle hash
			# wait for new deeds
			return (False, 'outside_curve_order')

		# check if bundle_hash exists
		sel = 'SELECT id FROM bundles WHERE bundle_hash = ?'
		if cursor.execute(sel, (bundle_hash,)).fetchone():
			return (False, 'dupe_bundle')

		# create address
		k = BitcoinPrivateKey(bundle_hash)
		address = k.public_key().address()
		wif = k.to_wif()		

		# make transaction
		# will block if wallet is not up to date
		try:
			tx = self.make_tx(address)
		except:
			return (False, 'mktx_fail')
		txid = tx.hash()

		# mark deeds as bundled
		ids = ','.join(str(dh[1]) for dh in deed_hashes)
		mark_done = """UPDATE deeds SET bundled_at = ?, bundle_address= ? 
				WHERE bundle_address IS NULL AND id IN ({0})""".format(ids)
		cursor.execute(mark_done, (bundled_at, address))

		# save the bundle
		insert = 'INSERT INTO bundles VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)'
		cursor.execute(insert, (all_hashes, deed_count, bundle_hash, wif, address, txid, bundled_at, 0))

		# rename and move the temp_bundle
		subpath = '{0}/{1}'.format(self.config['bundle_path'], address[:2])
		if not os.path.exists(subpath):
			os.makedirs(subpath)
		dest = '{0}/{1}.rbundle'.format(subpath, address)
		os.rename(temp_path, dest)

		# commit db transactions
		self._commit()			

		# send the transaction
		if not self.dry_run:
			self.tx_queue.put(tx)

		return (True, (deed_count, address))
	
	def confirm_bundle(self):
		cursor = self.db.cursor()
		check_bundles = 'SELECT id, txid, bundle_hash, address, created_at FROM bundles WHERE confirmed_at = 0 ORDER BY created_at DESC LIMIT 1'
		row = cursor.execute(check_bundles).fetchone()
		if not row:
			return (False, 'no_unconfirmed')

		address = row['address']
		txid = row['txid']
		now = int(time.time())
		since_creation = now - row['created_at']
		conf, timestamp = self.wallet.verifier.get_confirmations(txid)

		if conf > 0 and conf >= self.config['tx_confirm']:
			update = 'UPDATE bundles SET confirmed_at = ? WHERE id = ?'
			cursor.execute(update, (int(timestamp), row['id']))
			self._commit()
			return (True, (address, txid))

		if since_creation > self.config['resend_tx_after']:
			# has the wallet even heard of this txid?
			with self.wallet.transaction_lock:
				if txid in self.wallet.transactions:
					# guess we are waiting for a slow block
					return (False, 'waiting_for_confirm')
				else:
					# wallet doesn't know about txid, maybe we should make a new tx
					pass

			try:
				new_tx = self.make_tx(address)
			except:
				return (False, 'retry_mktx_fail')
			new_txid = tx.hash()
			if txid != new_txid:
				update_txid = 'UPDATE bundles SET txid = ? WHERE id = ?'
				cursor.execute(update_txid, (new_txid, row['id']))
				self._commit()
			if not self.dry_run:
				self.tx_queue.put(new_tx)
			return (False, 'retried_tx')

		return (False, 'waiting_for_confirm')

	def status(self):
		cursor = self.db.cursor()
		sel = 'SELECT count(id) FROM deeds WHERE bundled_at = 0'
		row = cursor.execute(sel).fetchone()
		pending = row[0] if row else 0

		sel = 'SELECT created_at FROM bundles ORDER BY created_at DESC LIMIT 1'
		row = cursor.execute(sel).fetchone()
		last_bundle = row[0] if row else 0

		sel = 'SELECT count(id) FROM bundles WHERE confirmed_at = 0'
		row = cursor.execute(sel).fetchone()
		unconfirmed = row[0] if row else 0

		return (pending, last_bundle, unconfirmed)

	def find_deeds(self, url):
		url = raw_pastebin(url)
		r = requests.get(url)
		return self.save_deeds(r.content)

	def save_deeds(self, content):
		deeds, errors = self.parse_deeds(content)
		self.queue_deeds(deeds)
		return (len(deeds), errors)		

	def parse_deeds(self, content):
		filtered = []
		errors = defaultdict(int)
		# extract signed messages
		deeds = extract_gpg(content)
		if not deeds:
			return (filtered, errors)

		cursor = self.db.cursor()
		for deed in deeds:
			# hash deed
			dh = hashlib.sha256(deed)
			deed_hash = dh.hexdigest()
			# skip if deed already exists
			sel = 'SELECT id FROM deeds WHERE deed_hash = ?'
			if cursor.execute(sel, (deed_hash,)).fetchone():
				errors['dupe'] += 1
				continue
			# skip if deed is too big
			if len(deed) > self.config['max_deed_size']:
				errors['too_big'] += 1
				continue
			# make sure signature is valid and trusted
			result = self.gpg.verify(deed)
			if result.valid:
				# check if trusted
				if result.fingerprint in self.trusted:
					fingerprint = result.fingerprint
				elif result.pubkey_fingerprint in self.trusted:
					fingerprint = result.pubkey_fingerprint
				else:
					errors['untrusted'] += 1
					continue
				# parse deed title
				title = deed_title(deed)
				# encode hash
				b58_hash = b58encode(dh.digest())
				otc_name = self.trusted[fingerprint][0]
				data = (fingerprint, otc_name, deed_hash, b58_hash, deed, title)
				filtered.append(data)

			else:
				errors['invalid'] += 1

		return (filtered, errors)

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


