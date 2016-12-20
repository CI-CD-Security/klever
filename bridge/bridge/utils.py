#
# Copyright (c) 2014-2016 ISPRAS (http://www.ispras.ru)
# Institute for System Programming of the Russian Academy of Sciences
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os
import time
import shutil
import logging
import hashlib
import tarfile
import tempfile
import zipfile
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
from django.template.defaultfilters import filesizeformat
from django.test import Client, TestCase, override_settings
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from bridge.settings import MAX_FILE_SIZE, MEDIA_ROOT, LOGGING

BLOCKER = {}
GROUP_BLOCKER = {}
TESTS_DIR = 'Tests'

logger = logging.getLogger('bridge')


class InfoFilter(object):
    def __init__(self, level):
        self.__level = level

    def filter(self, log_record):
        return log_record.levelno == self.__level


for h in logger.handlers:
    if h.name == 'other':
        h.addFilter(InfoFilter(logging.INFO))


def print_exec_time(f):
    def wrapper(*args, **kwargs):
        start = now()
        res = f(*args, **kwargs)
        logger.info('%s: %s' % (f.__name__, now() - start))
        return res
    return wrapper


def unparallel(f):

    def wait_other(*args, **kwargs):
        if f.__name__ not in BLOCKER:
            BLOCKER[f.__name__] = 0
        while BLOCKER[f.__name__] == 1:
            time.sleep(0.1)
        BLOCKER[f.__name__] = 1
        res = f(*args, **kwargs)
        BLOCKER[f.__name__] = 0
        return res
    return wait_other


def unparallel_group(groups):
    def unparallel_inner(f):

        def block_access():
            for g in groups:
                if g not in GROUP_BLOCKER:
                    GROUP_BLOCKER[g] = 0
                if GROUP_BLOCKER[g] == 1:
                    return False
            return True

        def change_block(status):
            for g in groups:
                GROUP_BLOCKER[g] = status

        def wait(*args, **kwargs):
            while not block_access():
                time.sleep(0.1)
            change_block(1)
            res = f(*args, **kwargs)
            change_block(0)
            return res

        return wait

    return unparallel_inner


def file_checksum(f):
    md5 = hashlib.md5()
    while True:
        data = f.read(8 * 1024)
        if not data:
            break
        md5.update(data)
    f.seek(0)
    return md5.hexdigest()


def file_get_or_create(fp, filename, table, check_size=False):
    if check_size:
        file_size = fp.seek(0, os.SEEK_END)
        if file_size > MAX_FILE_SIZE:
            raise ValueError(
                _('Please keep the file size under {0} (the current file size is {1})'.format(
                    filesizeformat(MAX_FILE_SIZE),
                    filesizeformat(file_size)
                ))
            )
    fp.seek(0)
    check_sum = file_checksum(fp)
    try:
        return table.objects.get(hash_sum=check_sum), check_sum
    except ObjectDoesNotExist:
        db_file = table()
        db_file.file.save(filename, File(fp))
        db_file.hash_sum = check_sum
        db_file.save()
        return db_file, check_sum


# archive - django.core.files.File object
# Example: archive = File(open(<path>, mode='rb'))
# Note: files from requests are already File objects
def extract_tar_temp(archive):
    with tempfile.NamedTemporaryFile() as fp:
        for chunk in archive.chunks():
            fp.write(chunk)
        fp.seek(0)
        if os.path.splitext(archive.name)[-1] == '.gz':
            with tarfile.open(fileobj=fp, mode='r:gz', encoding='utf8') as tar:
                tmp_dir_name = tempfile.TemporaryDirectory()
                tar.extractall(tmp_dir_name.name)
            return tmp_dir_name
        elif os.path.splitext(archive.name)[-1] == '.zip':
            with zipfile.ZipFile(fp, mode='r') as zfp:
                tmp_dir_name = tempfile.TemporaryDirectory()
                zfp.extractall(tmp_dir_name.name)
            return tmp_dir_name
        raise ValueError('The archive type is not supported')


def unique_id():
    return hashlib.md5(now().strftime("%Y%m%d%H%M%S%f%z").encode('utf8')).hexdigest()


def tests_logging_conf():
    tests_logging = LOGGING.copy()
    cnt = 1
    for handler in tests_logging['handlers']:
        if 'filename' in tests_logging['handlers'][handler]:
            tests_logging['handlers'][handler]['filename'] = os.path.join(MEDIA_ROOT, TESTS_DIR, 'log%s.log' % cnt)
            cnt += 1
    return tests_logging


# Logging overriding does not work (does not override it for tests but override it after tests done)
# Maybe it's Django's bug (LOGGING=tests_logging_conf())
@override_settings(MEDIA_ROOT=os.path.join(MEDIA_ROOT, TESTS_DIR))
class KleverTestCase(TestCase):
    def setUp(self):
        if not os.path.exists(os.path.join(MEDIA_ROOT, TESTS_DIR)):
            os.makedirs(os.path.join(MEDIA_ROOT, TESTS_DIR).encode("utf8"))
        self.client = Client()
        super(KleverTestCase, self).setUp()

    def tearDown(self):
        super(KleverTestCase, self).tearDown()
        try:
            shutil.rmtree(os.path.join(MEDIA_ROOT, TESTS_DIR))
        except PermissionError:
            pass


def has_references(obj):
    for link in list(rel.get_accessor_name() for rel in getattr(obj, '_meta').get_all_related_objects()):
        if getattr(obj, link).count() > 0:
            return True
    return False


# Only extracting component log content uses max_size. If you add another usage, change error messages according to it.
class ArchiveFileContent(object):
    def __init__(self, report, file_name, max_size=None):
        self._report = report
        self._max_size = max_size
        self._name = file_name
        self.error = None
        try:
            self.content = self.__extract_file_content()
        except Exception as e:
            logger.exception("Error while extracting file from archive: %s" % e)
            self.error = 'Unknown error'

    def __extract_file_content(self):
        with self._report.archive as fp:
            arc_ext = os.path.splitext(fp.name)[-1]
            if arc_ext == '.gz':
                with tarfile.open(fileobj=fp, mode='r:gz', encoding='utf8') as arch:
                    for f in arch.getmembers():
                        if f.isreg():
                            if self._name is not None and f.name != self._name:
                                continue
                            file_extracted = arch.extractfile(f)
                            if self._max_size is not None:
                                file_extracted.seek(0, 2)
                                if file_extracted.tell() > self._max_size:
                                    self.error = _('The component log is huge and '
                                                   'can not be showed but you can download it')
                                    return None
                                file_extracted.seek(0)
                            self._name = f.name
                            return file_extracted.read().decode('utf8')
            elif arc_ext == '.zip':
                with zipfile.ZipFile(fp, 'r') as z:
                    file_content = z.read(self._name)
                    if self._max_size is not None:
                        if len(file_content) > self._max_size:
                            self.error = _('The component log is huge and can not be showed but you can download it')
                            return None
                    return file_content
            else:
                self.error = _('Archive type is not supported')
                return None
        self.error = _('Needed file was not found')
        return None
