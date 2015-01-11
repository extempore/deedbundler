# -*- coding: utf-8 -*-
import os
import sqlite3
import zlib
import time


class BundlerDB(object):

	def __init__(self, path):
		self.path = path

	def open_db(self):
		filename = self.path
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
				sha256_hash TEXT NOT NULL,
				b58_hash TEXT NOT NULL,
				raw BLOB NOT NULL,
				title TEXT,
				created_at INTEGER NOT NULL,
				bundled_at INTEGER,
				bundle_address TEXT)
				""")

		cursor.execute("""CREATE TABLE bundles (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				lite_bundle TEXT NOT NULL,
				num_deeds INTEGER NOT NULL,
				sha256_hash TEXT NOT NULL,
				wif TEXT NOT NULL,
				address TEXT NOT NULL,
				txid TEXT,
				created_at INTEGER NOT NULL,
				confirmed_at INTEGER,
				sendtx_at INTEGER)
				""")
		cursor.execute('CREATE INDEX d_b58 ON deeds (b58_hash)')
		cursor.execute('CREATE INDEX d_address ON deeds (bundle_address)')
		cursor.execute('CREATE INDEX b_address ON bundles (address)')
		self._commit()

	def close_db(self):
		self.db.close()

	def _commit(self):
		'''a commit wrapper to give it another few tries if it errors.
		which sometimes happens due to OperationalError: database is locked'''
		for i in xrange(15):
			try:
				self.db.commit()
			except:
				time.sleep(1)


	def save_deeds(self, deeds):
		if not deeds:
			return
		cursor = self.db.cursor()
		insert = 'INSERT INTO deeds VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)'

		for deed in deeds:
			# compress deed text before storing, need to uncompress when reading
			deed_blob = sqlite3.Binary(zlib.compress(deed['raw']))
			row = (
					deed['fingerprint'],
					deed['otc_name'],
					deed['sha256_hash'],
					deed['b58_hash'], 
					deed_blob,
					deed['title'],
					deed['created_at'],
					)
			cursor.execute(insert, row)

		self._commit()


	def save_bundle(self, bundle, deed_ids):
		cursor = self.db.cursor()

		# update deeds first
		ids = ','.join(str(i) for i in deed_ids)
		update = """UPDATE deeds 
					SET bundled_at = ?, bundle_address= ? 
					WHERE bundle_address IS NULL 
					AND id IN ({0})""".format(ids)
		cursor.execute(update, (bundle['created_at'], bundle['address']))

		# insert bundle
		bundle = (
				bundle['lite_bundle'],
				bundle['num_deeds'],
				bundle['sha256_hash'],
				bundle['wif'],
				bundle['address'],
				bundle['txid'],
				bundle['created_at'],
				bundle['sendtx_at'],
				)
		insert = 'INSERT INTO bundles VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, NULL, ?)'
		cursor.execute(insert, bundle)
		self._commit()

	def confirm_bundle(self, bundle_id, confirmed_at):
		update = 'UPDATE bundles SET confirmed_at = ? WHERE id = ?'
		cursor.execute(update, (confirmed_at, bundle_id))
		self._commit()

	def update_txid(self, bundle_id, txid, timestamp):
		update_txid = 'UPDATE bundles SET txid = ?, sendtx_at = ? WHERE id = ?'
		cursor.execute(update_txid, (txid, timestamp, bundle_id))
		self._commit()

	def pending_deeds(self, max_deeds):
		cursor = self.db.cursor()
		sel = 'SELECT * FROM deeds WHERE bundled_at IS NULL ORDER BY created_at ASC LIMIT {0}'.format(max_deeds)
		rows = cursor.execute(sel)
		return rows

	def last_bundle(self):
		cursor = self.db.cursor()
		sel = 'SELECT * FROM bundles ORDER BY created_at DESC LIMIT 1'
		row = cursor.execute(sel).fetchone()
		return row

	def last_unconfirmed_bundle(self):
		cursor = self.db.cursor()
		check_bundles = """SELECT * FROM bundles 
						   WHERE confirmed_at IS NULL 
						   ORDER BY created_at DESC LIMIT 1"""
		return cursor.execute(check_bundles).fetchone()


	def unconfirmed_count(self):
		cursor = self.db.cursor()
		sel = 'SELECT count(id) FROM bundles WHERE confirmed_at IS NULL'
		row = cursor.execute(sel).fetchone()
		return row[0]

	def pending_count(self):
		cursor = self.db.cursor()
		sel = 'SELECT count(id), min(created_at) FROM deeds WHERE bundled_at IS NULL'
		row = cursor.execute(sel).fetchone()
		return row

	def deed_exists(self, b58_hash):
		cursor = self.db.cursor()
		sel = 'SELECT id FROM deeds WHERE b58_hash = ?'
		return cursor.execute(sel, (b58_hash,)).fetchone()

	def bundle_exists(self, sha256_hash):
		cursor = self.db.cursor()
		sel = 'SELECT id FROM bundles WHERE sha256_hash = ?'
		return cursor.execute(sel, (sha256_hash,)).fetchone()

