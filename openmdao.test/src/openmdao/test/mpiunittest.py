"""
A simple unit testing framework for MPI programs.
"""

import os
import sys

import numpy

from unittest import TestCase, TestResult, SkipTest
from openmdao.util.fileutil import get_module_path

try:
    from mpi4py import MPI
except ImportError:
    MPI = None


def _under_mpirun():
    """Return True if we're being executed under mpirun."""
    # TODO: this is a bit of a hack and there appears to be
    # no consistent set of environment vars between MPI 
    # implementations.
    for name in os.environ.keys():
        if name.startswith('OMPI_COMM') or name.startswith('MPICH_'):
            return True
    return False

class MPITestResult(TestResult):
    def __init__(self, stream=None, descriptions=None, verbosity=None):
        
    def addError(self, test, err):
        ???

class MPITestCase(TestCase):
    """A base class for all TestCases that are
    intended to run under MPI.
    """
    # A class attribute 'NCPUS' must be defined
    # for each MPITestCase class in order to 
    # know how big to make the MPI communicator.
    # NCPUS = 4
    def __init__(self, methodName='runTest'):
        super(MPITestCase, self).__init__(methodName)

        # save the original test method so the wrapper
        # will know what to call
        self._orig_testmethod_name = self._testMethodName

        if not _under_mpirun():
            self._testMethodName = '_test_non_mpi_method_wrapper'
            
    def _test_non_mpi_method_wrapper(self):
        """A wrapper we put around every test method
        when we're run normally (non-MPI), so that we can
        then kick off N mpi processes running that test
        method.
        """
        if MPI is None:
            raise SkipTest("mpi4py not installed")

    def run(self, result=None):
        info = {
            'failures': [],
            'errors': [],
            'skipped': [],
            'expectedFailures': [],
            'unexpectedSuccesses': [],
        }

        if result is None:
            result = self.defaultTestResult()
            startTestRun = getattr(result, 'startTestRun', None)
            if startTestRun is not None:
                startTestRun()

        try:
            if _under_mpirun():
                self.comm = MPI.Comm.Get_parent()

                try:
                    super(MPITestCase, self).run(result)
                except Exception as err:
                    print str(err)

                for key in info.keys():
                    for tcase, msg in getattr(result, key):
                        info[key].append(msg)

                # send results back to the mothership
                self.comm.gather(info, root=0)
                    
            else:
                testpath = '.'.join((self.__class__.__module__, 
                                     self.__class__.__name__,
                                     self._orig_testmethod_name))

                self.comm = MPI.COMM_SELF.Spawn(sys.executable, 
                                    args=['-m', 'openmdao.test.mpiunittest', testpath], 
                                    maxprocs=self.NCPUS)

                # gather results from spawned MPI processes
                infos = self.comm.gather(info, root=MPI.ROOT)

                self._testMethodName = self._orig_testmethod_name

                for key in info.keys():
                    rset = set()
                    for rmap in infos:
                        
                        for k,v in rmap.items():
                            getattr(result, k).append((self,v))

                # for i,rmap in enumerate(infos):
                #     for k,v in rmap.items():
                #         print ">>%d: %s: %s<<" % (i,k,v)
        finally:
            self.comm.Disconnect()

if __name__ == '__main__':
    args = sys.argv[1:]
    testpath = args[0]

    parts = testpath.split('.')

    print "parts = %s" % parts

    try:
        method = parts[-1]
        testcase_classname = parts[-2]
        modname = '.'.join(parts[:-2])

        print "mod = %s" % modname
        print "tcase = %s" % testcase_classname
        print "method = %s" % method

        __import__(modname)
        mod = sys.modules[modname]

        tcase = getattr(mod, testcase_classname)(method)

        result = tcase.defaultTestResult()

        print "result initialized"

    except Exception as err:
        print str(err)
        if _under_mpirun():
            MPI.Comm.Get_parent().Disconnect()

    print "running test case"
    tcase.run(result)
    