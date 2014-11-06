# -*- coding: utf-8 -*-
import json


deeds_config = {
	'db_name': 'deeds.sqlite',
	'db_path': '/home/deedbot/app/data/db',
	'bundle_path': '/home/deedbot/app/data/bundles',
	'gpg_path': '/home/deedbot/app/data/gpg',

	'hostname': 'deeds.bitcoin-assets.com',
	'bundles_per_page': 20,
	'bundles_per_page_index': 10,
	'deeds_per_page': 20,
	'deeds_per_page_index': 10,

	'main_address': '1LAwrWMbPLLSpt7nkD5Jv1Yf4cwPhD98ny',

	'min_oldest_deed': 10*60,
	'min_bundle_interval': 60*60,
	'make_bundle_interval': 5*60,
	'confirm_bundle_interval': 1*60,
	'update_trust_interval': 6*60*60,

	'max_deed_size': 32*1024,
	'max_url_size': 256*1024,
	'max_unconfirmed_bundles': 0,
	'deeds_per_bundle': 32,
	
	'tx_amount': 10000,
	'tx_fee': 1000,
	'tx_confirm': 1,
	'resend_tx_after': 30*60,

	'wallet_pass': None,
	'electrum_config': {
		'electrum_path': '/home/deedbot/app/data/electrum',
		'portable': True,
		'daemon_port': 8001,
		'daemon_timeout': 30*60,
		'auto_cycle': True,
		}
	}

if __name__ == '__main__':

	with open('./deeds_config.json', 'w') as f:
		c = json.dumps(deeds_config, sort_keys=True, indent=2)
		f.write(c)

