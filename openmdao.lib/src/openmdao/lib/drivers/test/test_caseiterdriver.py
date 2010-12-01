"""
Test CaseIteratorDriver.
"""

import logging
import os
import pkg_resources
import sys
import time
import unittest
import nose

import random
import numpy.random as numpy_random

from openmdao.lib.datatypes.api import TraitError

from openmdao.main.api import Assembly, Component, Case, set_as_top
from openmdao.main.eggchecker import check_save_load
from openmdao.main.exceptions import RunStopped
from openmdao.main.resource import ResourceAllocationManager, ClusterAllocator

from openmdao.lib.datatypes.api import Float, Bool, Array
from openmdao.lib.caseiterators.listcaseiter import ListCaseIterator
from openmdao.lib.drivers.caseiterdriver import CaseIteratorDriver
from openmdao.lib.caserecorders.listcaserecorder import ListCaseRecorder

from openmdao.test.cluster import init_cluster

from openmdao.util.testutil import assert_raises

# Capture original working directory so we can restore in tearDown().
ORIG_DIR = os.getcwd()

# pylint: disable-msg=E1101


def rosen_suzuki(x):
    """ Evaluate polynomial from CONMIN manual. """
    return x[0]**2 - 5.*x[0] + x[1]**2 - 5.*x[1] + \
           2.*x[2]**2 - 21.*x[2] + x[3]**2 + 7.*x[3] + 50


class DrivenComponent(Component):
    """ Just something to be driven and compute results. """

    x = Array([1., 1., 1., 1.], iotype='in')
    y = Array([1., 1., 1., 1.], iotype='in')
    raise_error = Bool(False, iotype='in')
    stop_exec = Bool(False, iotype='in')
    rosen_suzuki = Float(0., iotype='out')
    sum_y = Float(0., iotype='out')
        
    def __init__(self, *args, **kwargs):
        super(DrivenComponent, self).__init__(*args, **kwargs)

    def execute(self):
        """ Compute results from input vector. """
        self.rosen_suzuki = rosen_suzuki(self.x)
        self.sum_y = sum(self.y)
        if self.raise_error:
            self.raise_exception('Forced error', RuntimeError)
        if self.stop_exec:
            self.parent.driver.stop()  # Only valid if sequential!


class MyModel(Assembly):
    """ Use CaseIteratorDriver with DrivenComponent. """

    def __init__(self, *args, **kwargs):
        super(MyModel, self).__init__(*args, **kwargs)
        self.add('driver', CaseIteratorDriver())
        self.add('driven', DrivenComponent())
        self.driver.workflow.add('driven')


class TestCase(unittest.TestCase):
    """ Test CaseIteratorDriver. """

    # Need to be in this directory or there are issues with egg loading.
    directory = pkg_resources.resource_filename('openmdao.lib.drivers', 'test')

    def setUp(self):
        random.seed(10)
        numpy_random.seed(10)
        
        os.chdir(self.directory)
        self.model = set_as_top(MyModel())
        self.generate_cases()

    def generate_cases(self, force_errors=False):
        self.cases = []
        for i in range(10):
            raise_error = force_errors and i%4 == 3
            inputs = [('driven.x', None, numpy_random.normal(size=4)),
                      ('driven.y', None, numpy_random.normal(size=10)),
                      ('driven.raise_error', None, raise_error),
                      ('driven.stop_exec', None, False)]
            outputs = [('driven.rosen_suzuki', None, None),
                       ('driven.sum_y', None, None)]
            self.cases.append(Case(inputs, outputs, ident=i))

    def tearDown(self):
        self.model.pre_delete()
        self.model = None

        # Verify we didn't mess-up working directory.
        end_dir = os.getcwd()
        os.chdir(ORIG_DIR)
        if end_dir.lower() != self.directory.lower():
            self.fail('Ended in %s, expected %s' % (end_dir, self.directory))

    def test_sequential(self):
        logging.debug('')
        logging.debug('test_sequential')
        self.run_cases(sequential=True)

    def test_sequential_errors(self):
        logging.debug('')
        logging.debug('test_sequential_errors')
        self.generate_cases(force_errors=True)
        self.run_cases(sequential=True, forced_errors=True)

    def test_run_stop_step_resume(self):
        logging.debug('')
        logging.debug('test_run_stop_step_resume')

        self.generate_cases()
        stop_case = self.cases[1]  # Stop after 2 cases run.
        stop_case.inputs[3] = ('driven.stop_exec', None, True)
        self.model.driver.iterator = ListCaseIterator(self.cases)
        results = ListCaseRecorder()
        self.model.driver.recorder = results
        self.model.driver.sequential = True

        try:
            self.model.run()
        except RunStopped:
            self.assertEqual(len(results), 2)
            self.verify_results()
        else:
            self.fail('Expected RunStopped')

        self.model.driver.step()
        self.assertEqual(len(results), 3)
        self.verify_results()

        self.model.driver.step()
        self.assertEqual(len(results), 4)
        self.verify_results()

        self.model.driver.resume()
        self.assertEqual(len(results), len(self.cases))
        self.verify_results()

        try:
            self.model.driver.resume()
        except RuntimeError as exc:
            self.assertEqual(str(exc), 'driver: Run already complete')
        else:
            self.fail('Expected RuntimeError')

    def test_concurrent(self):
        # This can always test using a LocalAllocator (forked processes).
        # It can also use a ClusterAllocator if the environment looks OK.
        logging.debug('')
        logging.debug('test_concurrent')
        init_cluster(encrypted=True)
        self.run_cases(sequential=False)

    def test_concurrent_errors(self):
        logging.debug('')
        logging.debug('test_concurrent_errors')
        init_cluster(encrypted=True)
        self.generate_cases(force_errors=True)
        self.run_cases(sequential=False, forced_errors=True)

    def test_unencrypted(self):
        logging.debug('')
        logging.debug('test_unencrypted')
        name = init_cluster(encrypted=False)
        self.model.driver.extra_reqs = {'allocator': name}
        self.run_cases(sequential=False)

    def run_cases(self, sequential, forced_errors=False):
        """ Evaluate cases, either sequentially or across multiple servers. """
        self.model.driver.sequential = sequential
        self.model.driver.iterator = ListCaseIterator(self.cases)
        results = ListCaseRecorder()
        self.model.driver.recorder = results

        self.model.run()

        self.assertEqual(len(results), len(self.cases))
        self.verify_results(forced_errors)

    def verify_results(self, forced_errors=False):
        """ Verify recorded results match expectations. """
        for case in self.model.driver.recorder.cases:
            i = case.ident  # Correlation key.
            error_expected = forced_errors and i%4 == 3
            if error_expected:
                if self.model.driver.sequential:
                    self.assertEqual(case.msg, 'driven: Forced error')
                else:
                    self.assertEqual(case.msg, 'driven: Forced error')
            else:
                self.assertEqual(case.msg, None)
                self.assertEqual(case.outputs[0][2],
                                 rosen_suzuki(case.inputs[0][2]))
                self.assertEqual(case.outputs[1][2],
                                 sum(case.inputs[1][2]))

    def test_save_load(self):
        logging.debug('')
        logging.debug('test_save_load')

        self.model.driver.iterator = ListCaseIterator(self.cases)
        results = ListCaseRecorder()
        self.model.driver.recorder = results

        # Set local dir in case we're running in a different directory.
        py_dir = self.directory

        # Exercise check_save_load().
        retcode = check_save_load(self.model, py_dir=py_dir)
        self.assertEqual(retcode, 0)

    def test_noinput(self):
        logging.debug('')
        logging.debug('test_noinput')

        # Create cases with missing input 'dc.z'.
        cases = []
        for i in range(2):
            inputs = [('driven.x', None, numpy_random.normal(size=4)),
                      ('driven.z', None, numpy_random.normal(size=10))]
            outputs = [('driven.rosen_suzuki', None, None),
                       ('driven.sum_y', None, None)]
            cases.append(Case(inputs, outputs))

        self.model.driver.iterator = ListCaseIterator(cases)
        results = ListCaseRecorder()
        self.model.driver.recorder = results

        self.model.run()

        self.assertEqual(len(results), len(cases))
        msg = "driver: Exception setting 'driven.z':" \
              " driven: object has no attribute 'z'"
        for case in results.cases:
            self.assertEqual(case.msg, msg)

    def test_nooutput(self):
        logging.debug('')
        logging.debug('test_nooutput')

        # Create cases with missing output 'dc.sum_z'.
        cases = []
        for i in range(2):
            inputs = [('driven.x', None, numpy_random.normal(size=4)),
                      ('driven.y', None, numpy_random.normal(size=10))]
            outputs = [('driven.rosen_suzuki', None, None),
                       ('driven.sum_z', None, None)]
            cases.append(Case(inputs, outputs))

        self.model.driver.iterator = ListCaseIterator(cases)
        results = ListCaseRecorder()
        self.model.driver.recorder = results

        self.model.run()

        self.assertEqual(len(results), len(cases))
        msg = "driver: Exception getting 'driven.sum_z': " \
            "driven: object has no attribute 'sum_z'"
        for case in results.cases:
            self.assertEqual(case.msg, msg)

    def test_noiterator(self):
        logging.debug('')
        logging.debug('test_noiterator')

        # Check resoponse to no iterator set.
        self.model.driver.recorder = ListCaseRecorder()
        try:
            self.model.run()
        except ValueError as exc:
            msg = "driver: iterator has not been set"
            self.assertEqual(str(exc), msg)
        else:
            self.fail('ValueError expected')

    def test_norecorder(self):
        logging.debug('')
        logging.debug('test_norecorder')

        # Check response to no recorder set.
        self.model.driver.iterator = ListCaseIterator([])
        self.model.run()

    def test_noresource(self):
        logging.debug('')
        logging.debug('test_noresource')

        # Check response to unsupported resource.
        self.model.driver.extra_reqs = {'no-such-resource': 0}
        self.model.driver.sequential = False
        self.model.driver.iterator = ListCaseIterator([])
        assert_raises(self, 'self.model.run()', globals(), locals(),
                      RuntimeError,
                      'driver: No servers supporting required resources')


if __name__ == '__main__':
    sys.argv.append('--cover-package=openmdao.drivers')
    sys.argv.append('--cover-erase')
    nose.runmodule()

