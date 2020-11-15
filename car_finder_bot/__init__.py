# -*- coding: utf-8 -*-
# Owner: Bulat <bulat.kurbangaliev@cinarra.com>
import logging

__author__ = 'ilov3'

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s :: %(levelname)s: %(name)s: %(funcName)s: %(lineno)d: %(message)s')
logging.getLogger('telegram').setLevel(logging.INFO)
