# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import tempfile
import unittest

import shutil

from commons.compat import Path
from parse_1c_build.cli import get_argparser
from parse_1c_build.parse import run as parse_run


class MainTestCase(unittest.TestCase):
    def setUp(self):
        self.parser = get_argparser()

    def test_parse(self):
        temp_dir_path = Path(tempfile.mkdtemp())
        args = self.parser.parse_args('parse tests/data/test.epf {0}'.format(temp_dir_path).split())
        parse_run(args)
        shutil.rmtree(str(temp_dir_path))
