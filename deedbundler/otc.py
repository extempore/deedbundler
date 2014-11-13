# -*- coding: utf-8 -*-
import re
import sqlite3
from collections import defaultdict

import requests
import gnupg


class OTCDatabase(object):
	gpg_file = 'GPG.db'
	rating_file = 'RatingSystem.db'

	def __init__(self, path):
		self.path = path

	def open_db(self):
		gpg_path = '{0}/{1}'.format(self.path, self.gpg_file)
		self.gdb = sqlite3.connect(gpg_path, check_same_thread=False)
		self.gdb.row_factory = sqlite3.Row
		rating_path = '{0}/{1}'.format(self.path, self.rating_file)
		self.rdb = sqlite3.connect(rating_path, check_same_thread=False)
		self.rdb.row_factory = sqlite3.Row

	def close_db(self):
		self.gdb.close()
		self.rdb.close()

	def update_db(self):
		g = self.update_rating_db()
		r = self.update_gpg_db()

	def update_rating_db(self):
		filename = '{0}/{1}'.format(self.path, self.rating_file)
		url = 'http://bitcoin-otc.com/otc/RatingSystem.db'
		r = requests.get(url, stream=True)
		if r.status_code == 200:
			with open(filename, 'wb') as f:
				for chunk in r.iter_content(10*1024):
					f.write(chunk)
				return True
		else:
			return False

	def update_gpg_db(self):
		filename = '{0}/{1}'.format(self.path, self.gpg_file)
		url = 'http://bitcoin-otc.com/otc/GPG.db'
		r = requests.get(url, stream=True)
		if r.status_code == 200:
			with open(filename, 'wb') as f:
				for chunk in r.iter_content(10*1024):
					f.write(chunk)
				return True
		else:
			return False

	def assbot_trust(self):
		assbot_ratings = defaultdict(int)
		trusted = {}

		sel = """SELECT nick, rated_user_id, rater_user_id, rating FROM ratings
			 JOIN users ON ratings.rated_user_id = users.id
			 WHERE rater_user_id = 5506 OR rater_user_id IN (SELECT rated_user_id FROM ratings WHERE rater_user_id = 5506)
			"""
		cursor = self.rdb.cursor()
		cursor.execute(sel)
		results = cursor.fetchall()
		
		for row in results:
			add = 1 if row['rating'] > 0 else -1
			assbot_ratings[ row['nick'] ] += add

		selkey = 'SELECT fingerprint FROM users WHERE lower(nick) = ? AND fingerprint IS NOT NULL'
		gcursor = self.gdb.cursor()

		for nick in assbot_ratings:
			if  assbot_ratings[nick] > 0:
				row = gcursor.execute(selkey, (nick.lower(),)).fetchone()
				if row:
					trusted[ row['fingerprint'] ] = (nick, assbot_ratings[nick])
		return trusted



## make gpg pubring
class GPGManager(object):

	def __init__(self, gpghome, keyserver=None):
		self.gpghome = gpghome
		self.keyserver = keyserver if keyserver else 'hkp://pool.sks-keyservers.net'

		self.notfound = re.compile('key ([^ ]+) not found on keyserver')

		self.gpg = gnupg.GPG(homedir=gpghome)
		self.gpg.keyserver = self.keyserver

	def recv_keys(self, fingerprints, batch=10):
		not_found = []
		imported = 0
		for chunk in chunks(fingerprints, batch):
			r = self.gpg.recv_keys(*chunk)

			missing = self.notfound.findall(r.data)
			for k in missing:
				if k in chunk: not_found.append(k)

			imported += r.counts['imported']

		return (imported, not_found)

	def verify(self, data):
		return self.gpg.verify(data)

	def delete_keys(self, fingerprints):
		return self.gpg.delete_keys(fingerprints)


def chunks(l, n):
	""" Yield successive n-sized chunks from l."""
	for i in xrange(0, len(l), n):
		yield l[i:i+n]


