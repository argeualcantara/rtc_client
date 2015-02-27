from distutils.core import setup as distSetup, Extension

import os, os.path, sys

class RtcClientSetup(object):
	def setup(self):
		distSetup(name='RtcClient', version='1.0', py_modules=['RTC_CLIENT', 'xml2obj', 'config'])

RtcClientSetup().setup()
