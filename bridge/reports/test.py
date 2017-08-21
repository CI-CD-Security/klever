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
import json
import random

from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.test import Client

from bridge.vars import SCHEDULER_TYPE, JOB_STATUS, JOB_ROLES, JOB_CLASSES, FORMAT, COMPARE_VERDICT
from bridge.utils import KleverTestCase
from bridge.populate import populate_users

from users.models import User
from jobs.models import Job
from reports.models import ReportSafe, ReportUnsafe, ReportUnknown, ReportComponent, ReportComponentLeaf,\
    CompareJobsInfo, CompareJobsCache


# TODO: test 'jobs:download_file_for_compet', 'upload_job' after decision

LINUX_ATTR = {'Linux kernel': [{'version': '3.5.0'}, {'architecture': 'x86_64'}, {'configuration': 'allmodconfig'}]}
LKVOG_ATTR = {'LKVOG strategy': [{'name': 'separate modules'}]}
COMPUTER = [
    {"node name": "hellwig.intra.ispras.ru"},
    {"CPU model": "Intel(R) Core(TM) i7-3770 CPU @ 3.40GHz"},
    {"number of CPU cores": 8},
    {"memory size": 16808734720},
    {"Linux kernel version": "3.16.7-29-default"},
    {"architecture": "x86_64"}
]
CHUNKS1 = [
    {
        'attrs': [
            {'Verification object': 'drivers/usb/core/usb1.ko'},
            {'Rule specification': 'linux:mutex'}
        ],
        'tool_attrs': [{'Bug kind': 'unsafe bug:kind1'}],
        'tool': 'BLAST 2.7.2',
        'unsafes': ['unsafe1.zip', 'unsafe2.zip'],
        'unknown': 'unknown2.zip'
    },
    {
        'attrs': [
            {'Verification object': 'drivers/usb/core/usb1.ko'},
            {'Rule specification': 'linux:rule1'}
        ],
        'tool_attrs': [{'Bug kind': 'unsafe bug:kind1'}],
        'tool': 'BLAST 2.7.2',
        'unsafes': ['unsafe3.zip']
    },
    {
        'attrs': [
            {'Verification object': 'drivers/usb/core/usb2.ko'},
            {'Rule specification': 'linux:mutex'}
        ],
        'tool_attrs': [{'Bug kind': 'unsafe bug:kind1'}],
        'tool': 'BLAST 2.7.2',
        'safe': 'safe.zip'
    },
    {
        'attrs': [
            {'Verification object': 'drivers/usb/core/usb3.ko'},
            {'Rule specification': 'linux:mutex'}
        ],
        'tool_attrs': [{'Bug kind': 'unsafe bug:kind1'}],
        'tool': 'CPAchecker',
        'unsafes': ['unsafe4.zip']
    },
    {
        'attrs': [
            {'Verification object': 'drivers/usb/core/usb4.ko'},
            {'Rule specification': 'linux:rule1'}
        ],
        'fail': 'EMG',
        'unknown': 'unknown0.zip'
    },
    {
        'attrs': [
            {'Verification object': 'drivers/usb/core/usb5.ko'},
            {'Rule specification': 'linux:mutex'}
        ],
        'tool_attrs': [{'Bug kind': 'unsafe bug:kind1'}],
        'tool': 'BLAST 2.7.2',
        'unsafes': ['unsafe5.zip', 'unsafe6.zip'],
        'unknown': 'unknown1.zip'
    },
    {
        'attrs': [
            {'Verification object': 'drivers/usb/core/usb6.ko'},
            {'Rule specification': 'linux:mutex'}
        ],
        'fail': 'SA',
        'unknown': 'unknown3.zip'
    }
]
CHUNKS2 = [
    {
        'attrs': [
            {'Verification object': 'drivers/usb/core/usb1.ko'},
            {'Rule specification': 'linux:mutex'}
        ],
        'tool_attrs': [{'Bug kind': 'unsafe bug:kind1'}],
        'tool': 'BLAST 2.7.2',
        'unknown': 'unknown1.zip'
    },
    {
        'attrs': [
            {'Verification object': 'drivers/usb/core/usb2.ko'},
            {'Rule specification': 'linux:mutex'}
        ],
        'tool_attrs': [{'Bug kind': 'unsafe bug:kind1'}],
        'tool': 'BLAST 2.7.2',
        'safe': 'safe.zip'
    },
    {
        'attrs': [
            {'Verification object': 'drivers/usb/core/usb3.ko'},
            {'Rule specification': 'linux:mutex'}
        ],
        'tool_attrs': [{'Bug kind': 'unsafe bug:kind1'}],
        'tool': 'CPAchecker',
        'unsafes': ['unsafe7.zip']
    },
    {
        'attrs': [
            {'Verification object': 'drivers/usb/core/usb4.ko'},
            {'Rule specification': 'linux:rule1'}
        ],
        'tool_attrs': [{'Bug kind': 'unsafe bug:kind1'}],
        'tool': 'CPAchecker',
        'unsafes': ['unsafe8.zip']
    },
    {
        'attrs': [
            {'Verification object': 'drivers/usb/core/usb5.ko'},
            {'Rule specification': 'linux:mutex'}
        ],
        'tool_attrs': [{'Bug kind': 'unsafe bug:kind1'}],
        'tool': 'BLAST 2.7.2',
        'unsafes': ['unsafe9.zip', 'unsafe10.zip'],
        'unknown': 'unknown1.zip'
    },
    {
        'attrs': [
            {'Verification object': 'drivers/usb/core/usb6.ko'},
            {'Rule specification': 'linux:mutex'}
        ],
        'tool_attrs': [{'Bug kind': 'unsafe bug:kind1'}],
        'tool': 'BLAST 2.7.2',
        'safe': 'safe.zip'
    }
]

CHUNKS3 = [
    {
        'attrs': [
            {'Verification object': 'drivers/usb/core/usb.ko'},
            {'Rule specification': 'linux:mutex'}
        ],
        'tool_attrs': [{'Bug kind': 'unsafe bug:kind1'}],
        'tool': 'BLAST 2.7.2',
        'unsafes': ['unsafe_check.zip']
    }
]

ARCHIVE_PATH = os.path.join(settings.BASE_DIR, 'reports', 'test_files')


def resources():
    return {
        'CPU time': random.randint(100, 10000),
        'memory size': random.randint(10**7, 10**9),
        'wall time': random.randint(100, 10000)
    }


class TestReports(KleverTestCase):
    def setUp(self):
        super(TestReports, self).setUp()
        self.service_client = Client()
        User.objects.create_superuser('superuser', '', 'top_secret')
        populate_users(
            admin={'username': 'superuser'},
            manager={'username': 'manager', 'password': '12345'},
            service={'username': 'service', 'password': 'service'}
        )
        self.client.post(reverse('users:login'), {'username': 'superuser', 'password': 'top_secret'})
        self.client.post(reverse('population'))
        self.client.get(reverse('users:logout'))
        self.client.post(reverse('users:login'), {'username': 'manager', 'password': '12345'})

    def test_reports(self):
        self.ids_in_use = []
        self.job = Job.objects.order_by('parent').first()
        if self.job is None:
            self.fail('Jobs are not populated')

        # Run decision
        run_conf = json.dumps([
            ["HIGH", "0", "rule specifications"], ["1", "2.0", "2.0"], [1, 1, 100, '', 15, None],
            [
                "INFO", "%(asctime)s (%(filename)s:%(lineno)03d) %(name)s %(levelname)5s> %(message)s",
                "NOTSET", "%(name)s %(levelname)5s> %(message)s"
            ],
            [False, True, True, False, True, False, '0']
        ])
        self.client.post('/jobs/ajax/run_decision/', {'job_id': self.job.pk, 'data': run_conf})

        # Service sign in and check session parameters
        response = self.service_client.post('/users/service_signin/', {
            'username': 'service', 'password': 'service',
            'job identifier': self.job.identifier,
            'scheduler': SCHEDULER_TYPE[0][1]
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8')
        self.assertEqual(self.service_client.session.get('scheduler'), SCHEDULER_TYPE[0][0])
        self.assertEqual(self.service_client.session.get('job id'), self.job.pk)

        self.__decide_job()
        main_report = ReportComponent.objects.get(parent=None, root__job_id=self.job.pk)

        response = self.client.get(reverse('reports:component', args=[self.job.pk, main_report.pk]))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('reports:unsafes', args=[main_report.pk]))
        if ReportUnsafe.objects.count() == 1:
            self.assertRedirects(response, reverse('reports:unsafe', args=[ReportUnsafe.objects.first().id]))
        else:
            self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('reports:safes', args=[main_report.pk]))
        if ReportSafe.objects.count() == 1:
            self.assertRedirects(response, reverse('reports:safe', args=[ReportSafe.objects.first().id]))
        else:
            self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('reports:unknowns', args=[main_report.pk]))
        if ReportUnknown.objects.count() == 1:
            self.assertRedirects(response, reverse('reports:unknown', args=[ReportUnknown.objects.first().id]))
        else:
            self.assertEqual(response.status_code, 200)

        for report in ReportComponent.objects.filter(~Q(parent=None) & Q(root__job_id=self.job.pk)):
            response = self.client.get(reverse('reports:component', args=[self.job.pk, report.pk]))
            self.assertEqual(response.status_code, 200)
            # TODO: update archives so that all unsafes can be shown without errors and uncomment it
            # response = self.client.get(reverse('reports:unsafes', args=[report.pk]))
            # leaves = ReportComponentLeaf.objects.exclude(unsafe=None).filter(report=report)
            # if leaves.count() == 1:
            #     self.assertRedirects(response, reverse('reports:unsafe', args=[leaves.first().unsafe_id]))
            # else:
            #     self.assertEqual(response.status_code, 200)
            response = self.client.get(reverse('reports:safes', args=[report.pk]))
            leaves = ReportComponentLeaf.objects.exclude(safe=None).filter(report=report)
            if leaves.count() == 1:
                self.assertRedirects(response, reverse('reports:safe', args=[leaves.first().safe_id]))
            else:
                self.assertEqual(response.status_code, 200)
            response = self.client.get(reverse('reports:unknowns', args=[report.pk]))
            leaves = ReportComponentLeaf.objects.exclude(unknown=None).filter(report=report)
            if leaves.count() == 1:
                self.assertRedirects(response, reverse('reports:unknown', args=[leaves.first().unknown_id]))
            else:
                self.assertEqual(response.status_code, 200)
            response = self.client.get(
                '%s?component=%s' % (reverse('reports:unknowns', args=[report.pk]), report.component_id)
            )
            leaves = ReportComponentLeaf.objects.exclude(unknown=None)\
                .filter(report=report, unknown__component_id=report.component_id)
            if leaves.count() == 1:
                self.assertRedirects(response, reverse('reports:unknown', args=[leaves.first().unknown_id]))
            else:
                self.assertEqual(response.status_code, 200)
        for report in ReportUnknown.objects.all():
            response = self.client.get(reverse('reports:unknown', args=[report.pk]))
            self.assertEqual(response.status_code, 200)
        # TODO: update archives so that all unsafes can be shown without errors and uncomment it
        # for report in ReportUnsafe.objects.all():
        #     response = self.client.get(reverse('reports:unsafe', args=[report.pk]))
        #     self.assertEqual(response.status_code, 200)
        #     response = self.client.get(reverse('reports:etv', args=[report.pk]))
        #     self.assertEqual(response.status_code, 200)
        for report in ReportSafe.objects.all():
            response = self.client.get(reverse('reports:safe', args=[report.pk]))
            self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('reports:download_files', args=[main_report.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')

        # TODO: test get_source(); we can get source code file name by downloading raw error trace json
        # But firstly we need to aupdate unsafe archives
        # unsafe = ReportUnsafe.objects.all()[0]
        # ArchiveFileContent(unsafe, source_name).content
        # response = self.client.post('/reports/ajax/get_source/', {
        #     'report_id': unsafe.pk, 'file_name': afc._name
        # })
        # self.assertEqual(response.status_code, 200)
        # self.assertEqual(response['Content-Type'], 'application/json')
        # self.assertNotIn('error', json.loads(str(response.content, encoding='utf8')))

        response = self.client.post('/reports/logcontent/%s/' % main_report.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8')

        response = self.client.post(reverse('reports:log', args=[main_report.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')

        # Collapse job
        response = self.client.post('/jobs/ajax/collapse_reports/', {'job_id': self.job.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(response.content, encoding='utf8')))

        self.assertEqual(len(ReportSafe.objects.filter(root__job=self.job)), 1)
        self.assertEqual(
            len(ReportComponent.objects.filter(Q(root__job=self.job) & ~Q(parent__parent=None) & ~Q(parent=None))), 0
        )

        run_conf = json.dumps([
            ["HIGH", "0", "rule specifications"], ["1", "2.0", "2.0"], [1, 1, 100, '', 15, None],
            [
                "INFO", "%(asctime)s (%(filename)s:%(lineno)03d) %(name)s %(levelname)5s> %(message)s",
                "NOTSET", "%(name)s %(levelname)5s> %(message)s"
            ],
            [False, True, True, False, True, False, '1']
        ])
        self.client.post('/jobs/ajax/run_decision/', {'job_id': self.job.pk, 'data': run_conf})
        DecideJobs('service', 'service', CHUNKS1)
        self.assertEqual(len(ReportSafe.objects.filter(root__job=self.job)), 1)
        self.assertEqual(
            len(ReportComponent.objects.filter(Q(root__job=self.job) & ~Q(parent__parent=None) & ~Q(parent=None))), 0
        )

    def test_comparison(self):
        try:
            # Exclude jobs "Validation on commits" due to they need additional attribute for comparison: "Commit"
            job1 = Job.objects.filter(~Q(parent=None) & ~Q(type=JOB_CLASSES[1][0]))[0]
        except IndexError:
            job1 = Job.objects.filter(~Q(type=JOB_CLASSES[1][0]))[0]

        response = self.client.post('/jobs/ajax/savejob/', {
            'title': 'New job title',
            'description': 'Description of new job',
            'global_role': JOB_ROLES[0][0],
            'user_roles': '[]',
            'parent_identifier': job1.identifier,
            'file_data': '[]'
        })
        job2 = Job.objects.get(pk=int(json.loads(str(response.content, encoding='utf8'))['job_id']))
        self.client.post('/jobs/ajax/fast_run_decision/', {'job_id': job1.pk})
        DecideJobs('service', 'service', CHUNKS1)
        self.client.post('/jobs/ajax/fast_run_decision/', {'job_id': job2.pk})
        DecideJobs('service', 'service', CHUNKS2)
        response = self.client.post('/reports/ajax/fill_compare_cache/', {'job1': job1.pk, 'job2': job2.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(response.content, encoding='utf8')))
        try:
            comparison = CompareJobsInfo.objects.get(
                user__username='manager', root1__job_id=job1.pk, root2__job_id=job2.pk
            )
        except ObjectDoesNotExist:
            self.fail('Comparsion cache is empty')

        # 6 modules (1 module veridfied by 2 rules)
        self.assertEqual(len(CompareJobsCache.objects.filter(info=comparison)), 7)

        response = self.client.get(reverse('reports:comparison', args=[job1.pk, job2.pk]))
        self.assertEqual(response.status_code, 200)

        response = self.client.post('/reports/ajax/get_compare_jobs_data/', {
            'info_id': comparison.pk, 'verdict': '%s_%s' % (COMPARE_VERDICT[0][0], COMPARE_VERDICT[0][0])
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8')

        response = self.client.get(reverse('jobs:comparison', args=[job1.pk, job2.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8')

    def __get_report_id(self, name):
        r_id = '/' + name
        while r_id in self.ids_in_use:
            r_id = '/%s%s' % (name, random.randint(1, 100))
        self.ids_in_use.append(r_id)
        return r_id

    def __upload_start_report(self, name, parent, attrs=None):
        r_id = self.__get_report_id(name)
        report = {'id': r_id, 'type': 'start', 'parent id': parent, 'name': name}
        if attrs is not None:
            report['attrs'] = attrs
        response = self.service_client.post('/reports/upload/', {'report': json.dumps(report)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(response.content, encoding='utf8')))
        self.assertEqual(len(ReportComponent.objects.filter(
            root__job_id=self.job.pk,
            identifier=self.job.identifier + r_id,
            parent__identifier=self.job.identifier + parent,
            component__name=name,
            finish_date=None
        )), 1)
        return r_id

    def __upload_finish_report(self, r_id):
        with open(os.path.join(ARCHIVE_PATH, 'report.zip'), mode='rb') as fp:
            response = self.service_client.post('/reports/upload/', {
                'report': json.dumps({
                    'id': r_id, 'type': 'finish', 'resources': resources(),
                    'log': 'log.txt', 'desc': 'It does not matter'
                }), 'report files archive': fp
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(response.content, encoding='utf8')))
        self.assertIsNotNone(ReportComponent.objects.get(identifier=self.job.identifier + r_id).finish_date)

    def __upload_attrs_report(self, r_id, attrs):
        response = self.service_client.post('/reports/upload/', {
            'report': json.dumps({'id': r_id, 'type': 'attrs', 'attrs': attrs})
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(response.content, encoding='utf8')))

    def __upload_data_report(self, r_id, data=None):
        if data is None:
            data = {"newdata": str(random.randint(0, 100))}

        response = self.service_client.post('/reports/upload/', {
            'report': json.dumps({'id': r_id, 'type': 'data', 'data': data})
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(response.content, encoding='utf8')))

    def __upload_verification_report(self, name, parent, attrs=None):
        r_id = self.__get_report_id(name)
        report = {
            'id': r_id, 'type': 'verification', 'parent id': parent, 'name': name,
            'resources': resources(), 'data': {'description': str(r_id)}, 'log': 'log.txt'
        }
        if isinstance(attrs, list):
            report['attrs'] = attrs

        with open(os.path.join(ARCHIVE_PATH, 'report.zip'), mode='rb') as fp:
            response = self.service_client.post('/reports/upload/', {
                'report': json.dumps(report), 'report files archive': fp
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(response.content, encoding='utf8')))
        self.assertEqual(len(ReportComponent.objects.filter(Q(
            root__job_id=self.job.pk, identifier=self.job.identifier + r_id,
            parent__identifier=self.job.identifier + parent, component__name=name, finish_date=None
        ))), 1)
        return r_id

    def __upload_finish_verification_report(self, r_id):
        response = self.service_client.post('/reports/upload/', {
            'report': json.dumps({'id': r_id, 'type': 'verification finish'})
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(response.content, encoding='utf8')))
        self.assertEqual(len(ReportComponent.objects.filter(
            Q(root__job_id=self.job.pk, identifier=self.job.identifier + r_id) & ~Q(finish_date=None)
        )), 1)

    def __upload_unknown_report(self, parent, archive):
        r_id = self.__get_report_id('unknown')
        report = {'id': r_id, 'type': 'unknown', 'parent id': parent, 'problem desc': 'problem description.txt'}
        with open(os.path.join(ARCHIVE_PATH, archive), mode='rb') as fp:
            response = self.service_client.post('/reports/upload/', {
                'report': json.dumps(report), 'report files archive': fp
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(response.content, encoding='utf8')))
        self.assertEqual(len(ReportUnknown.objects.filter(
            root__job_id=self.job.pk, identifier=self.job.identifier + r_id,
            parent__identifier=self.job.identifier + parent
        )), 1)

    def __upload_safe_report(self, parent, attrs, archive):
        r_id = self.__get_report_id('safe')
        with open(os.path.join(ARCHIVE_PATH, archive), mode='rb') as fp:
            response = self.service_client.post('/reports/upload/', {'report': json.dumps({
                'id': r_id, 'type': 'safe', 'parent id': parent, 'proof': 'proof.txt', 'attrs': attrs
            }), 'report files archive': fp})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(response.content, encoding='utf8')))
        self.assertEqual(len(ReportSafe.objects.filter(
            root__job_id=self.job.pk, identifier=self.job.identifier + r_id,
            parent__identifier=self.job.identifier + parent
        )), 1)

    def __upload_unsafe_report(self, parent, attrs, archive):
        r_id = self.__get_report_id('unsafe')
        with open(os.path.join(ARCHIVE_PATH, archive), mode='rb') as fp:
            response = self.service_client.post('/reports/upload/', {'report': json.dumps({
                'id': r_id, 'type': 'unsafe', 'parent id': parent,
                'error trace': 'error trace.json', 'attrs': attrs
            }), 'report files archive': fp})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(response.content, encoding='utf8')))
        self.assertEqual(len(ReportUnsafe.objects.filter(
            root__job_id=self.job.pk, identifier=self.job.identifier + r_id,
            parent__identifier=self.job.identifier + parent
        )), 1)

    def __decide_job(self):
        sch_data = {
            'tasks': {'pending': [], 'processing': [], 'error': [], 'finished': [], 'cancelled': []},
            'task errors': {},
            'task descriptions': {},
            'task solutions': {},
            'jobs': {'pending': [], 'processing': [], 'error': [], 'finished': [], 'cancelled': []},
            'job errors': {},
            'job configurations': {}
        }
        response = self.service_client.post('/service/get_jobs_and_tasks/', {
            'jobs and tasks status': json.dumps(sch_data)
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        res = json.loads(str(response.content, encoding='utf8'))
        self.assertNotIn('error', res)
        self.assertIn('jobs and tasks status', res)
        res_data = json.loads(res['jobs and tasks status'])
        try:
            self.assertIn(self.job.identifier, res_data['jobs']['pending'])
            self.assertIn(self.job.identifier, res_data['job configurations'])
        except KeyError:
            self.fail('Wrong result format')

        response = self.service_client.post('/jobs/decide_job/', {'report': json.dumps({
            'type': 'start', 'id': '/', 'attrs': [{'PSI version': 'stage-2-1k123j13'}], 'comp': COMPUTER
        }), 'job format': FORMAT})
        self.assertIn(response['Content-Type'], {'application/x-zip-compressed', 'application/zip'})
        self.assertEqual(Job.objects.get(pk=self.job.pk).status, JOB_STATUS[2][0])

        core_data1 = None
        core_data2 = None
        if self.job.type == JOB_CLASSES[0][0]:
            core_data1 = {
                'module1': {
                    'ideal verdict': 'safe',
                    'verification status': 'unsafe',
                    'comment': 'This is comment for module1'
                },
                'module2': {
                    'ideal verdict': 'safe',
                    'verification status': 'safe'
                }
            }
            core_data2 = {
                'module3': {
                    'ideal verdict': 'unsafe',
                    'verification status': 'unsafe',
                    'comment': 'This is comment for module3'
                },
                'module4': {
                    'ideal verdict': 'unsafe',
                    'verification status': 'unknown'
                }
            }
        elif self.job.type == JOB_CLASSES[1][0]:
            core_data1 = {
                'module1': {
                    'before fix': {'verification status': 'unsafe', 'comment': 'Comment for module1 before fix'},
                    'after fix': {'verification status': 'unsafe', 'comment': 'Comment for module1 after fix'},
                },
                'module2': {
                    'before fix': {'verification status': 'safe'},
                    'after fix': {'verification status': 'unsafe', 'comment': 'Comment for module2 after fix'},
                }
            }
            core_data2 = {
                'module3': {
                    'before fix': {'verification status': 'unsafe', 'comment': 'Comment for module3 before fix'},
                    'after fix': {'verification status': 'safe'},
                },
                'module4': {
                    'before fix': {'verification status': 'unsafe'}, 'after fix': {'verification status': 'unknown'},
                }
            }

        self.__upload_data_report('/', core_data1)
        self.__upload_data_report('/', core_data2)

        lkbce = self.__upload_start_report('LKBCE', '/')
        self.__upload_attrs_report(lkbce, [LINUX_ATTR])
        self.__upload_finish_report(lkbce)

        lkvog = self.__upload_start_report('LKVOG', '/', [LKVOG_ATTR])
        self.__upload_finish_report(lkvog)

        avtg = self.__upload_start_report('AVTG', '/', [LINUX_ATTR])
        vtg = self.__upload_start_report('VTG', '/', [LINUX_ATTR, LKVOG_ATTR])

        for chunk in CHUNKS1:
            sa = self.__upload_start_report('SA', avtg, chunk['attrs'])
            self.__upload_data_report(sa)
            self.__upload_finish_report(sa)
            if 'fail' in chunk and chunk['fail'] == 'SA':
                self.__upload_unknown_report(sa, chunk['unknown'])
                continue
            emg = self.__upload_start_report('EMG', avtg, chunk['attrs'])
            self.__upload_finish_report(emg)
            if 'fail' in chunk and chunk['fail'] == 'EMG':
                self.__upload_unknown_report(emg, chunk['unknown'])
                continue
            rsg = self.__upload_start_report('RSG', avtg, chunk['attrs'])
            self.__upload_finish_report(rsg)
            if 'fail' in chunk and chunk['fail'] == 'RSG':
                self.__upload_unknown_report(rsg, chunk['unknown'])
                continue
            abkm = self.__upload_start_report('ABKM', avtg, chunk['attrs'])
            if 'fail' in chunk and chunk['fail'] == 'ABKM':
                self.__upload_finish_report(abkm)
                self.__upload_unknown_report(sa, chunk['unknown'])
                continue
            cnt = 1
            if 'safe' in chunk:
                tool = self.__upload_verification_report(chunk['tool'], abkm, chunk['tool_attrs'])
                self.__upload_safe_report(tool, [], chunk['safe'])
                self.__upload_finish_verification_report(tool)
            elif 'unsafes' in chunk:
                for u_arch in chunk['unsafes']:
                    tool = self.__upload_verification_report(chunk['tool'], abkm, chunk['tool_attrs'])
                    self.__upload_unsafe_report(tool, [{'entry point': 'any_function_%s' % cnt}], u_arch)
                    self.__upload_finish_verification_report(tool)
                    cnt += 1
            if 'unknown' in chunk and 'safe' not in chunk:
                tool = self.__upload_verification_report(chunk['tool'], abkm, chunk['tool_attrs'])
                self.__upload_unknown_report(tool, chunk['unknown'])
                self.__upload_finish_verification_report(tool)
            self.__upload_finish_report(abkm)

        self.__upload_finish_report(avtg)
        self.__upload_finish_report(vtg)
        self.__upload_finish_report('/')

        new_sch_data = sch_data.copy()
        new_sch_data['jobs']['finished'].append(self.job.identifier)
        response = self.service_client.post('/service/get_jobs_and_tasks/', {
            'jobs and tasks status': json.dumps(new_sch_data)
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(Job.objects.get(pk=self.job.pk).status, JOB_STATUS[3][0])


class DecideJobs(object):
    def __init__(self, username, password, reports_data):
        self.service = Client()
        self.username = username
        self.password = password
        self.reports_data = reports_data
        self.ids_in_use = []
        self.__upload_reports()

    def __upload_reports(self):
        scheduler = Client()
        scheduler.post('/users/service_signin/', {
            'username': self.username, 'password': self.password, 'scheduler': SCHEDULER_TYPE[0][1]
        })
        sch_data = {
            'tasks': {'pending': [], 'processing': [], 'error': [], 'finished': [], 'cancelled': []},
            'task errors': {}, 'task descriptions': {}, 'task solutions': {},
            'jobs': {'pending': [], 'processing': [], 'error': [], 'finished': [], 'cancelled': []},
            'job errors': {}, 'job configurations': {}
        }
        response = scheduler.post('/service/get_jobs_and_tasks/', {'jobs and tasks status': json.dumps(sch_data)})
        res_data = json.loads(json.loads(str(response.content, encoding='utf8'))['jobs and tasks status'])

        for job_identifier in res_data['jobs']['pending']:
            self.service.post('/users/service_signin/', {
                'username': self.username, 'password': self.password, 'job identifier': job_identifier
            })
            self.__decide_job(job_identifier)
            self.service.post('/users/service_signout/')
            sch_data['jobs']['finished'].append(job_identifier)
        scheduler.post('/service/get_jobs_and_tasks/', {'jobs and tasks status': json.dumps(sch_data)})
        scheduler.post('/users/service_signout/')

    def __get_report_id(self, name):
        r_id = '/' + name
        while r_id in self.ids_in_use:
            r_id = '/%s%s' % (name, random.randint(1, 100))
        self.ids_in_use.append(r_id)
        return r_id

    def __upload_start_report(self, name, parent, attrs=None):
        r_id = self.__get_report_id(name)
        report = {'id': r_id, 'type': 'start', 'parent id': parent, 'name': name}
        if attrs is not None:
            report['attrs'] = attrs
        self.service.post('/reports/upload/', {'report': json.dumps(report)})
        return r_id

    def __upload_finish_report(self, r_id):
        with open(os.path.join(ARCHIVE_PATH, 'report.zip'), mode='rb') as fp:
            self.service.post('/reports/upload/', {
                'report': json.dumps({
                    'id': r_id, 'type': 'finish', 'resources': resources(),
                    'log': 'log.txt', 'desc': 'It does not matter'
                }), 'report files archive': fp
            })

    def __upload_attrs_report(self, r_id, attrs):
        self.service.post('/reports/upload/', {
            'report': json.dumps({'id': r_id, 'type': 'attrs', 'attrs': attrs})
        })

    def __upload_data_report(self, r_id, data=None):
        if data is None:
            data = {"newdata": str(random.randint(0, 100))}
        self.service.post('/reports/upload/', {
            'report': json.dumps({'id': r_id, 'type': 'data', 'data': data})
        })

    def __upload_verification_report(self, name, parent, attrs, report_arch='report.zip', coverage='full_coverage.zip'):
        r_id = self.__get_report_id(name)
        report = {
            'id': r_id, 'type': 'verification', 'parent id': parent, 'name': name, 'resources': resources(),
            'data': {'description': str(r_id)}, 'coverage': 'coverage.json'
        }
        if isinstance(attrs, list):
            report['attrs'] = attrs

        with open(os.path.join(ARCHIVE_PATH, coverage), mode='rb') as cfp:
            if random.randint(1, 10) > 4:
                report['log'] = 'log.txt'
                with open(os.path.join(ARCHIVE_PATH, report_arch), mode='rb') as fp:
                    self.service.post('/reports/upload/', {
                        'report': json.dumps(report), 'report files archive': fp, 'coverage files archive': cfp
                    })
            else:
                self.service.post('/reports/upload/', {'report': json.dumps(report), 'coverage files archive': cfp})
        return r_id

    def __upload_finish_verification_report(self, r_id):
        self.service.post('/reports/upload/', {'report': json.dumps({'id': r_id, 'type': 'verification finish'})})

    def __upload_unknown_report(self, parent, archive, finish_parent=True):
        r_id = self.__get_report_id('unknown')
        report = {'id': r_id, 'type': 'unknown', 'parent id': parent, 'problem desc': 'problem description.txt'}
        with open(os.path.join(ARCHIVE_PATH, archive), mode='rb') as fp:
            self.service.post('/reports/upload/', {'report': json.dumps(report), 'report files archive': fp})
        if finish_parent:
            self.__upload_finish_report(parent)

    def __upload_safe_report(self, parent, attrs, archive):
        r_id = self.__get_report_id('safe')
        with open(os.path.join(ARCHIVE_PATH, archive), mode='rb') as fp:
            self.service.post('/reports/upload/', {'report': json.dumps({
                'id': r_id, 'type': 'safe', 'parent id': parent, 'proof': 'proof.txt', 'attrs': attrs
            }), 'report files archive': fp})

    def __upload_empty_safe_report(self, parent, attrs):
        self.service.post('/reports/upload/', {'report': json.dumps({
            'id': self.__get_report_id('safe'), 'type': 'safe', 'parent id': parent, 'proof': None, 'attrs': attrs
        })})

    def __upload_unsafe_report(self, parent, attrs, archive):
        r_id = self.__get_report_id('unsafe')
        with open(os.path.join(ARCHIVE_PATH, archive), mode='rb') as fp:
            self.service.post('/reports/upload/', {'report': json.dumps({
                'id': r_id, 'type': 'unsafe', 'parent id': parent,
                'error trace': 'error trace.json', 'attrs': attrs
            }), 'report files archive': fp})

    def __decide_job(self, job_identifier):
        self.service.post('/jobs/decide_job/', {'report': json.dumps({
            'type': 'start', 'id': '/', 'attrs': [{'PSI version': 'version-1'}], 'comp': COMPUTER
        }), 'job format': FORMAT})

        core_data = None
        job = Job.objects.get(identifier=job_identifier)
        if job.type == JOB_CLASSES[0][0]:
            core_data = {
                'module1': {
                    'ideal verdict': 'safe',
                    'verification status': 'unsafe',
                    'comment': 'This is comment for module1'
                },
                'module2': {
                    'ideal verdict': 'safe',
                    'verification status': 'safe'
                },
                'module3': {
                    'ideal verdict': 'unsafe',
                    'verification status': 'unsafe',
                    'comment': 'This is comment for module3'
                },
                'module4': {
                    'ideal verdict': 'unsafe',
                    'verification status': 'unknown'
                }
            }
        elif job.type == JOB_CLASSES[1][0]:
            core_data = {
                'module1': {
                    'before fix': {'verdict': 'unsafe', 'comment': 'Comment for module1 before fix'},
                    'after fix': {'verdict': 'unsafe', 'comment': 'Comment for module1 after fix'},
                },
                'module2': {
                    'before fix': {'verdict': 'safe', 'comment': '1'},
                    'after fix': {'verdict': 'unsafe', 'comment': 'Comment for module2 after fix'},
                },
                'module3': {
                    'before fix': {'verdict': 'unsafe', 'comment': 'Comment for module3 before fix'},
                    'after fix': {'verdict': 'safe', 'comment': '1'},
                },
                'module4': {
                    'before fix': {'verdict': 'unsafe', 'comment': '1'},
                    'after fix': {'verdict': 'unknown', 'comment': '1'},
                }
            }

        self.__upload_data_report('/', core_data)

        lkbce = self.__upload_start_report('LKBCE', '/')
        self.__upload_attrs_report(lkbce, [LINUX_ATTR])
        self.__upload_finish_report(lkbce)

        lkvog = self.__upload_start_report('LKVOG', '/', [LKVOG_ATTR])
        self.__upload_finish_report(lkvog)

        avtg = self.__upload_start_report('AVTG', '/', [LINUX_ATTR])
        vtg = self.__upload_start_report('VTG', '/', [LINUX_ATTR, LKVOG_ATTR])

        for chunk in self.reports_data:
            if job.type == JOB_CLASSES[1][0]:
                chunk['attrs'].append({'Commit': 'HEAD'})

            sa = self.__upload_start_report('SA', avtg, chunk['attrs'])
            self.__upload_data_report(sa)
            if 'fail' in chunk and chunk['fail'] == 'SA':
                self.__upload_unknown_report(sa, chunk['unknown'])
                continue
            self.__upload_finish_report(sa)

            emg = self.__upload_start_report('EMG', avtg, chunk['attrs'])
            if 'fail' in chunk and chunk['fail'] == 'EMG':
                self.__upload_unknown_report(emg, chunk['unknown'])
                continue
            self.__upload_finish_report(emg)

            rsg = self.__upload_start_report('RSG', avtg, chunk['attrs'])
            if 'fail' in chunk and chunk['fail'] == 'RSG':
                self.__upload_unknown_report(rsg, chunk['unknown'])
                continue
            self.__upload_finish_report(rsg)

            abkm = self.__upload_start_report('ABKM', avtg, chunk['attrs'])
            if 'fail' in chunk and chunk['fail'] == 'ABKM':
                self.__upload_unknown_report(abkm, chunk['unknown'])
                continue
            cnt = 1
            if 'safe' in chunk:
                tool = self.__upload_verification_report(chunk['tool'], abkm, chunk['tool_attrs'])
                self.__upload_safe_report(tool, [], chunk['safe'])
                self.__upload_finish_verification_report(tool)
                # self.__upload_empty_safe_report(tool, [])
            elif 'unsafes' in chunk:
                for u_arch in chunk['unsafes']:
                    tool = self.__upload_verification_report(
                        chunk['tool'], abkm, chunk['tool_attrs'], coverage='big_full_coverage.zip'
                    )
                    self.__upload_unsafe_report(tool, [{'entry point': 'any_function_%s' % cnt}], u_arch)
                    self.__upload_finish_verification_report(tool)
                    cnt += 1
            if 'unknown' in chunk and 'safe' not in chunk:
                tool = self.__upload_verification_report(
                    chunk['tool'], abkm, chunk['tool_attrs'], coverage='partially_coverage.zip'
                )
                self.__upload_unknown_report(tool, chunk['unknown'], False)
                self.__upload_finish_verification_report(tool)
            self.__upload_finish_report(abkm)

        self.__upload_finish_report(avtg)
        self.__upload_finish_report(vtg)
        self.__upload_finish_report('/')
