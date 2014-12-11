"""
Test for CSVCaseRecorder and CSVCaseIterator.
"""
import glob, os, time
import StringIO
import unittest

from numpy import array

from openmdao.lib.casehandlers.api import CSVCaseIterator, CSVCaseRecorder, \
                                          DumpCaseRecorder
from openmdao.main.datatypes.api import Array, Str, Bool, VarTree, Float
from openmdao.lib.drivers.api import SimpleCaseIterDriver
from openmdao.main.api import Assembly, Case, set_as_top, VariableTree, Component
from openmdao.test.execcomp import ExecComp
from openmdao.util.testutil import assert_raises
from openmdao.main.test.test_vartree import DumbVT
from openmdao.lib.drivers.conmindriver import CONMINdriver

class TestContainer(VariableTree):

    dummy1 = Float(desc='default value of 0.0') #this value is being grabbed by the optimizer
    dummy2 = Float(11.0)


class TestComponent(Component):

    dummy_data = VarTree(TestContainer(), iotype='in')
    x = Float(iotype='out')

    def execute(self):
        self.x = (self.dummy_data.dummy1-3)**2 - self.dummy_data.dummy2


class TestAssembly(Assembly):

    def configure(self):
        self.add('dummy_top', TestContainer())
        self.add('comp', TestComponent())
        self.add('driver', CONMINdriver())

        self.driver.workflow.add(['comp'])
        #self.driver.iprint = 4 #debug verbosity
        self.driver.add_objective('comp.x')
        self.driver.add_parameter('comp.dummy_data.dummy1', low=-10.0, high=10.0)

class TestCase(unittest.TestCase):
    def setUp(self):
        self.filename = "openmdao_test_csv_case_iterator.csv"

    def tearDown(self):
        for recorder in self.top.recorders:
            recorder.close()
        if os.path.exists(self.filename):
            os.remove(self.filename)

    def test_flatten(self):
        self.top = set_as_top(TestAssembly())
        self.top.recorders = [CSVCaseRecorder(filename=self.filename)]
        self.top.run()
        cases = [case for case in self.top.recorders[0].get_iterator()]
        end_case = cases[-1]
        #end_case.get_input('comp.dummy_data.dummy1')
        self.assertAlmostEqual(end_case.get_input('comp.dummy_data.dummy1'), 3.0, 1) #3.0 should be minimum

    def test_inoutCSV(self):
        self.top = set_as_top(TestAssembly())
        self.top.recorders = [CSVCaseRecorder(filename=self.filename)]
        self.top.run()
        
        # now use the CSV recorder as source of Cases
        cases = [case for case in self.top.recorders[0].get_iterator()]
        driver = self.top.add('driver', SimpleCaseIterDriver())
        Case.set_vartree_inputs(self.top.driver, cases)

        sout = StringIO.StringIO()
        self.top.recorders = [DumpCaseRecorder(sout)]
        driver.add_responses(['comp.x',])
        self.top.run()
        
        # Check the results
        expected = [
            'Case:',
            '   uuid: f18c0e94-8005-11e4-804e-20c9d0478eff',
            '   timestamp: 1418172374.364364',
            '   inputs:',
            '      comp.dummy_data.dummy1: 0.0333333393814',
            '   outputs:',
            '      Response(comp.x): -2.19888892477',
            '      _pseudo_1.out0: -2.19888892477',
            '      comp.derivative_exec_count: 0',
            '      comp.exec_count: 46',
            '      comp.itername: 4-comp',
            '      comp.x: -2.19888892477',
            '      driver.workflow.itername: 4',
            ]
        
        lines = sout.getvalue().split('\n')
        count = 0
        for index, line in enumerate(lines):
            if line.startswith('Case:'):
                count += 1
                if count != 4:
                    continue
                for i in range(len(expected)):
                    if expected[i].startswith('   uuid:'):
                        self.assertTrue(lines[index+i].startswith('   uuid:'))
                    elif expected[i].startswith('   timestamp:'):
                        self.assertTrue(lines[index+i].startswith('   timestamp:'))
                    else:
                        self.assertEqual(lines[index+i], expected[i])
                break
        else:
            self.fail("couldn't find the expected Case")
        
    def test_inoutCSV_delimiter(self):

        # Repeat test above using semicolon delimiter and ' as quote char.

        self.top = set_as_top(TestAssembly())
        self.top.recorders = [CSVCaseRecorder(filename=self.filename,
                                              delimiter=';', quotechar="'")]
        self.top.run()
        
        # now use the CSV recorder as source of Cases
        cases = [case for case in self.top.recorders[0].get_iterator()]
        driver = self.top.add('driver', SimpleCaseIterDriver())
        Case.set_vartree_inputs(self.top.driver, cases)

        sout = StringIO.StringIO()
        self.top.recorders = [DumpCaseRecorder(sout)]
        driver.add_responses(['comp.x',])
        self.top.run()
        
        # Check the results
        expected = [
            'Case:',
            '   uuid: f18c0e94-8005-11e4-804e-20c9d0478eff',
            '   timestamp: 1418172374.364364',
            '   inputs:',
            '      comp.dummy_data.dummy1: 0.0333333393814',
            '   outputs:',
            '      Response(comp.x): -2.19888892477',
            '      _pseudo_1.out0: -2.19888892477',
            '      comp.derivative_exec_count: 0',
            '      comp.exec_count: 46',
            '      comp.itername: 4-comp',
            '      comp.x: -2.19888892477',
            '      driver.workflow.itername: 4',
            ]
        
        lines = sout.getvalue().split('\n')
        count = 0
        for index, line in enumerate(lines):
            if line.startswith('Case:'):
                count += 1
                if count != 4:
                    continue
                for i in range(len(expected)):
                    if expected[i].startswith('   uuid:'):
                        self.assertTrue(lines[index+i].startswith('   uuid:'))
                    elif expected[i].startswith('   timestamp:'):
                        self.assertTrue(lines[index+i].startswith('   timestamp:'))
                    else:
                        self.assertEqual(lines[index+i], expected[i])
                break
        else:
            self.fail("couldn't find the expected Case")

class CSVCaseRecorderTestCase(unittest.TestCase):

    def setUp(self):
        self.top = top = set_as_top(Assembly())
        driver = top.add('driver', SimpleCaseIterDriver())
        top.add('comp1', ExecComp(exprs=['z=x+y']))
        top.add('comp2', ExecComp(exprs=['z=x+1']))
        top.connect('comp1.z', 'comp2.x')
        top.comp1.add('a_string', Str("Hello',;','", iotype='out'))
        top.comp1.add('a_array', Array(array([1.0, 3.0, 5.5]), iotype='out'))
        top.comp1.add('x_array', Array(array([1.0, 1.0, 1.0]), iotype='in'))
        top.comp1.add('b_bool', Bool(False, iotype='in'))
        top.comp1.add('vt', VarTree(DumbVT(), iotype='out'))
        top.driver.workflow.add(['comp1', 'comp2'])

        # now create some Cases
        outputs = ['comp1.z', 'comp2.z', 'comp1.a_string', 'comp1.a_array[2]']
        cases = []
        for i in range(10):
            i = float(i)
            inputs = [('comp1.x', i+0.1), ('comp1.y', i*2 + .1),
                      ('comp1.x_array[1]', 99.88), ('comp1.b_bool', True)]
            cases.append(Case(inputs=inputs, outputs=outputs))

        Case.set_vartree_inputs(driver, cases)
        driver.add_responses(sorted(outputs))

        self.filename = "openmdao_test_csv_case_iterator.csv"

    def tearDown(self):
        for recorder in self.top.recorders:
            recorder.close()
        if os.path.exists(self.filename):
            os.remove(self.filename)

    #def test_inoutCSV(self):

        ##This test runs some cases, puts them in a CSV file using a
        ##CSVCaseRecorder, then runs the model again using the same cases,
        ##pulled out of the CSV file by a CSVCaseIterator.  Finally the cases
        ##are dumped to a string after being run for the second time.

        #self.top.recorders = [CSVCaseRecorder(filename=self.filename)]
        #self.top.recorders[0].num_backups = 0
        #self.top.run()

        ## now use the CSV recorder as source of Cases
        #cases = [case for case in self.top.recorders[0].get_iterator()]
        #Case.set_vartree_inputs(self.top.driver, cases)

        #sout = StringIO.StringIO()
        #self.top.recorders = [DumpCaseRecorder(sout)]
        #self.top.run()
        #expected = [
            #'Case:',
            #'   uuid: eacddff8-7326-11e4-8027-20c9d0478eff',
            #'   timestamp: 1416757171.328441',
            #'   inputs:',
            #'      comp1.b_bool: True',
            #'      comp1.x: 8.1',
            #'      comp1.x_array[1]: 99.88',
            #'      comp1.y: 16.1',
            #'   outputs:',
            #'      _pseudo_0.out0: 5.5',
            #"      _pseudo_1.out0: Hello',;','",
            #'      _pseudo_2.out0: 24.2',
            #'      _pseudo_3.out0: 25.2',
            #'      comp1.a_array[2]: 5.5',
            #"      comp1.a_string: Hello',;','",
            #'      comp1.z: 24.2',
            #'      comp2.z: 25.2',
            #'      driver.workflow.itername: 9',
            ##'Case:',
            ##'   uuid: ad4c1b76-64fb-11e0-95a8-001e8cf75fe',
            ##'   timestamp: 1383239074.309192',
            ##'   inputs:',
            ##'      comp1.b_bool: True',
            ##'      comp1.x: 8.1',
            ##'      comp1.x_array[1]: 99.88',
            ##'      comp1.y: 16.1',
            ##'   outputs:',
            ##'      Response(comp1.a_array[2]): 5.5',
            ##"      Response(comp1.a_string): Hello',;','",
            ##'      Response(comp1.z): 24.2',
            ##'      Response(comp2.z): 25.2',
            #]
##        print sout.getvalue()
        #lines = sout.getvalue().split('\n')
        #count = 0
        #for index, line in enumerate(lines):
            #if line.startswith('Case:'):
                #count += 1
                #if count != 9:
                    #continue
                #for i in range(len(expected)):
                    #if expected[i].startswith('   uuid:'):
                        #self.assertTrue(lines[index+i].startswith('   uuid:'))
                    #elif expected[i].startswith('   timestamp:'):
                        #self.assertTrue(lines[index+i].startswith('   timestamp:'))
                    #else:
                        #self.assertEqual(lines[index+i], expected[i])
                #break
        #else:
            #self.fail("couldn't find the expected Case")

    #def test_inoutCSV_delimiter(self):

        ##Repeat test above using semicolon delimiter and ' as quote char.

        #self.top.recorders = [CSVCaseRecorder(filename=self.filename,
                                              #delimiter=';', quotechar="'")]
        #self.top.recorders[0].num_backups = 0
        #self.top.run()

        ## now use the DB as source of Cases
        #self.top.driver.iterator = self.top.recorders[0].get_iterator()

        #sout = StringIO.StringIO()
        #self.top.recorders = [DumpCaseRecorder(sout)]
        #self.top.run()
        #expected = [
            #'Case:',
            #'   uuid: 85830647-7327-11e4-801d-20c9d0478eff',
            #'   timestamp: 1416757430.884792',
            #'   inputs:',
            #'      comp1.b_bool: True',
            #'      comp1.x: 8.1',
            #'      comp1.x_array[1]: 99.88',
            #'      comp1.y: 16.1',
            #'   outputs:',
            #'      _pseudo_0.out0: 5.5',
            #"      _pseudo_1.out0: Hello',;','",
            #'      _pseudo_2.out0: 24.2',
            #'      _pseudo_3.out0: 25.2',
            #'      comp1.a_array[2]: 5.5',
            #"      comp1.a_string: Hello',;','",
            #'      comp1.z: 24.2',
            #'      comp2.z: 25.2',
            #'      driver.workflow.itername: 9',
            ##'Case:',
            ##'   uuid: ad4c1b76-64fb-11e0-95a8-001e8cf75fe',
            ##'   timestamp: 1383239074.309192',
            ##'   inputs:',
            ##'      comp1.b_bool: True',
            ##'      comp1.x: 8.1',
            ##'      comp1.x_array[1]: 99.88',
            ##'      comp1.y: 16.1',
            ##'   outputs:',
            ##'      Response(comp1.a_array[2]): 5.5',
            ##"      Response(comp1.a_string): Hello',;','",
            ##'      Response(comp1.z): 24.2',
            ##'      Response(comp2.z): 25.2',
            #]
##        print sout.getvalue()
        #lines = sout.getvalue().split('\n')
        #count = 0
        #for index, line in enumerate(lines):
            #if line.startswith('Case:'):
                #count += 1
                #if count != 9:
                    #continue
                #for i in range(len(expected)):
                    #if expected[i].startswith('   uuid:'):
                        #self.assertTrue(lines[index+i].startswith('   uuid:'))
                    #elif expected[i].startswith('   timestamp:'):
                        #self.assertTrue(lines[index+i].startswith('   timestamp:'))
                    #else:
                        #self.assertEqual(lines[index+i], expected[i])
                #break
        #else:
            #self.fail("couldn't find the expected Case")


    def test_CSVCaseIterator_read_external_file_with_header(self):

        csv_data = ['"comp1.x", "comp1.y", "comp2.b_string"\n',
                    '33.5, 76.2, "Hello There"\n'
                    '3.14159, 0, "Goodbye z"\n'
                    ]

        outfile = open(self.filename, 'w')
        outfile.writelines(csv_data)
        outfile.close()

        self.top.comp2.add('b_string', Str("Hello',;','", iotype='in'))


        sout = StringIO.StringIO()
        cases = [case for case in CSVCaseIterator(filename=self.filename)]
        self.top.driver.clear_parameters()
        Case.set_vartree_inputs(self.top.driver, cases)
        self.top.recorders = [DumpCaseRecorder(sout)]
        self.top.run()

        self.assertEqual(self.top.comp1.x, 3.14159)
        self.assertEqual(self.top.comp1.y, 0.0)
        self.assertEqual(self.top.comp2.b_string, "Goodbye z")

    def test_CSVCaseIterator_read_external_file_without_header(self):

        csv_data = ['33.5, 76.2, "Hello There"\n'
                    '3.14159, 0, "Goodbye z"\n'
                    ]

        outfile = open(self.filename, 'w')
        outfile.writelines(csv_data)
        outfile.close()

        header_dict = {0 : "comp1.x",
                       1 : "comp1.y",
                       2 : "comp2.b_string"}

        self.top.comp2.add('b_string', Str("Hello',;','", iotype='in'))


        sout = StringIO.StringIO()
        cases = [case for case in CSVCaseIterator(filename=self.filename,
                                                  headers=header_dict)]
        self.top.driver.clear_parameters()
        Case.set_vartree_inputs(self.top.driver, cases)
        self.top.recorders = [DumpCaseRecorder(sout)]
        
        self.top.run()

        self.assertEqual(self.top.comp1.x, 3.14159)
        self.assertEqual(self.top.comp1.y, 0.0)
        self.assertEqual(self.top.comp2.b_string, "Goodbye z")

    def test_sorting(self):
        # Make sure outputs are sorted

        rec = CSVCaseRecorder(filename=self.filename)
        rec.num_backups = 0
        rec.startup()
        rec.register(self, ['comp1.x', 'comp1.y', 'comp2.x', ], [])
        rec.record(self, [2.0, 4.3, 1.9], [], None, '', '')
        rec.close()

        outfile = open(self.filename, 'r')
        csv_data = outfile.readlines()
        outfile.close()

        line = '"timestamp","/INPUTS","comp1.x","comp1.y","comp2.x",' \
               '"/OUTPUTS","/METADATA","uuid","parent_uuid","msg"\r\n'
        self.assertEqual(csv_data[0], line)
        line = '"",2.0,4.3,1.9,"","","","",""\r\n'
        self.assertTrue(csv_data[1].endswith(line))

#     def test_flatten(self):
#         # create some Cases

#         outputs = ['comp1.a_array', 'comp1.vt']
#         inputs = [('comp1.x_array', array([2.0, 2.0, 2.0]))]
#         cases = [Case(inputs=inputs, outputs=outputs)]
#         self.top.driver.clear_parameters()
#         Case.set_vartree_inputs(self.top.driver, cases)
#         self.top.driver.clear_responses()
#         self.top.driver.add_responses(outputs)
#         #self.top.recorders = [CSVCaseRecorder(filename=self.filename)]
#         from openmdao.lib.casehandlers.api import JSONCaseRecorder
#         self.top.recorders = [JSONCaseRecorder('flatten.json')]
#         self.top.recorders[0].num_backups = 0
#         self.top.run()

#         from openmdao.util.dotgraph import plot_graph
#         #plot_graph(self.top.driver.workflow._collapsed_graph)
#         plot_graph(self.top._reduced_graph)
        

#         # check recorded cases
#         cases = [case for case in self.top.recorders[0].get_iterator()]
#         sout = StringIO.StringIO()
#         for case in cases:
#             print >>sout, case
#         expected = [
#             'Case:',
#             '   uuid: b5e4fc5e-7324-11e4-800d-20c9d0478eff',
#             '   timestamp: 1416756223.565777',
#             '   inputs:',
#             '      comp1.x_array[0]: 2.0',
#             '      comp1.x_array[1]: 2.0',
#             '      comp1.x_array[2]: 2.0',
#             '   outputs:',
#             '      _pseudo_4.out0[0]: 1.0',
#             '      _pseudo_4.out0[1]: 3.0',
#             '      _pseudo_4.out0[2]: 5.5',
#             '      comp1.a_array[0]: 1.0',
#             '      comp1.a_array[1]: 3.0',
#             '      comp1.a_array[2]: 5.5',
#             '      comp1.vt.data: ',
#             '      comp1.vt.v1: 1.0',
#             '      comp1.vt.v2: 2.0',
#             '      comp1.vt.vt2.data: ',
#             '      comp1.vt.vt2.vt3.a: 1.0',
#             '      comp1.vt.vt2.vt3.b: 12.0',
#             '      comp1.vt.vt2.vt3.data: ',
#             '      comp1.vt.vt2.x: -1.0',
#             '      comp1.vt.vt2.y: -2.0',
#             '      comp1.z: 0.0',
#             '      driver.workflow.itername: 1',

#             #'Case:',
#             #'   uuid: ad4c1b76-64fb-11e0-95a8-001e8cf75fe',
#             #'   timestamp: 1383238593.781986',
#             #'   inputs:',
#             #'      comp1.x_array[0]: 2.0',
#             #'      comp1.x_array[1]: 2.0',
#             #'      comp1.x_array[2]: 2.0',
#             #'   outputs:',
#             #'      Response(comp1.a_array)[0]: 1.0',
#             #'      Response(comp1.a_array)[1]: 3.0',
#             #'      Response(comp1.a_array)[2]: 5.5',
#             #'      Response(comp1.vt).data: ',
#             #'      Response(comp1.vt).v1: 1.0',
#             #'      Response(comp1.vt).v2: 2.0',
#             #'      Response(comp1.vt).vt2.data: ',
#             #'      Response(comp1.vt).vt2.vt3.a: 1.0',
#             #'      Response(comp1.vt).vt2.vt3.b: 12.0',
#             #'      Response(comp1.vt).vt2.vt3.data: ',
#             #'      Response(comp1.vt).vt2.x: -1.0',
#             #'      Response(comp1.vt).vt2.y: -2.0',
#             #'      comp1.a_array[0]: 1.0',
#             #'      comp1.a_array[1]: 3.0',
#             #'      comp1.a_array[2]: 5.5',
#             #"      comp1.a_string: Hello',;','",
#             #'      comp1.derivative_exec_count: 0.0',
#             #'      comp1.exec_count: 1.0',
#             #'      comp1.itername: 1-comp1',
#             #'      comp1.vt.data: ',
#             #'      comp1.vt.v1: 1.0',
#             #'      comp1.vt.v2: 2.0',
#             #'      comp1.vt.vt2.data: ',
#             #'      comp1.vt.vt2.vt3.a: 1.0',
#             #'      comp1.vt.vt2.vt3.b: 12.0',
#             #'      comp1.vt.vt2.vt3.data: ',
#             #'      comp1.vt.vt2.x: -1.0',
#             #'      comp1.vt.vt2.y: -2.0',
#             #'      comp1.z: 0.0',
#             #'      comp2.derivative_exec_count: 0.0',
#             #'      comp2.exec_count: 1.0',
#             #'      comp2.itername: 1-comp2',
#             #'      comp2.z: 1.0',
#             #'      driver.workflow.itername: 1',
#             ]
#         expected = [
#             'Case:',
#             '   uuid: e57e3c19-798b-11e4-800d-20c9d0478eff',
#             '   timestamp: 1417460248.562843',
#             '   inputs:',
#             '      comp1.x_array[0]: 2.0',
#             '      comp1.x_array[1]: 2.0',
#             '      comp1.x_array[2]: 2.0',
#             '   outputs:',
#             '      Response(comp1.a_array)[0]: 1.0',
#             '      Response(comp1.a_array)[1]: 3.0',
#             '      Response(comp1.a_array)[2]: 5.5',
#             '      Response(comp1.vt).data: ',
#             '      Response(comp1.vt).v1: 1.0',
#             '      Response(comp1.vt).v2: 2.0',
#             '      Response(comp1.vt).vt2.data: ',
#             '      Response(comp1.vt).vt2.vt3.a: 1.0',
#             '      Response(comp1.vt).vt2.vt3.b: 12.0',
#             '      Response(comp1.vt).vt2.vt3.data: ',
#             '      Response(comp1.vt).vt2.x: -1.0',
#             '      Response(comp1.vt).vt2.y: -2.0',
#             '      comp1.derivative_exec_count: 0.0',
#             '      comp1.exec_count: 1.0',
#             '      comp1.itername: 1-comp1',
#             '      comp2.derivative_exec_count: 0.0',
#             '      comp2.exec_count: 1.0',
#             '      comp2.itername: 1-comp2',
#             '      driver.workflow.itername: 1',
#         ]

# #        print sout.getvalue()
#         lines = sout.getvalue().split('\n')
#         for index, line in enumerate(lines):
#             if line.startswith('Case:'):
#                 for i in range(len(expected)):
#                     if expected[i].startswith('   uuid:'):
#                         self.assertTrue(lines[index+i].startswith('   uuid:'))
#                     elif expected[i].startswith('   timestamp:'):
#                         self.assertTrue(lines[index+i].startswith('   timestamp:'))
#                     else:
#                         self.assertEqual(lines[index+i], expected[i])
#                 break
#         else:
#             self.fail("couldn't find the expected Case")

#         # now use the CSV recorder as source of Cases
#         self.top.driver.clear_parameters()
#         Case.set_vartree_inputs(self.top.driver, cases)
#         sout = StringIO.StringIO()
#         self.top.recorders = [DumpCaseRecorder(sout)]  # Dump not flattened.
#         self.top.run()
#         expected = [
#             'Case:',
#             '   uuid: 3b4e5c63-7325-11e4-800e-20c9d0478eff',
#             '   timestamp: 1416756447.395058',
#             '   inputs:',
#             '      comp1.x_array[0]: 2.0',
#             '      comp1.x_array[1]: 2.0',
#             '      comp1.x_array[2]: 2.0',
#             '   outputs:',
#             '      _pseudo_4.out0: [ 1.   3.   5.5]',
#             '      comp1.a_array: [ 1.   3.   5.5]',
#             '      comp1.vt.data: None',
#             '      comp1.vt.v1: 1.0',
#             '      comp1.vt.v2: 2.0',
#             '      comp1.vt.vt2.data: None',
#             '      comp1.vt.vt2.vt3.a: 1.0',
#             '      comp1.vt.vt2.vt3.b: 12.0',
#             '      comp1.vt.vt2.vt3.data: None',
#             '      comp1.vt.vt2.x: -1.0',
#             '      comp1.vt.vt2.y: -2.0',
#             '      comp1.z: 0.0',
#             '      driver.workflow.itername: 1',
#             #'   uuid: ad4c1b76-64fb-11e0-95a8-001e8cf75fe',
#             #'   timestamp: 1383238593.781986',
#             #'   inputs:',
#             #'      comp1.x_array[0]: 2.0',
#             #'      comp1.x_array[1]: 2.0',
#             #'      comp1.x_array[2]: 2.0',
#             #'   outputs:',
#             #'      Response(comp1.a_array): [ 1.   3.   5.5]',
#             #'      Response(comp1.vt): <openmdao.main.test.test_vartree.DumbVT object',
#             #'      comp1.a_array: [ 1.   3.   5.5]',
#             #"      comp1.a_string: Hello',;','",
#             #'      comp1.derivative_exec_count: 0',
#             #'      comp1.exec_count: 2',
#             #'      comp1.itername: 1-comp1',
#             #'      comp1.vt: <openmdao.main.test.test_vartree.DumbVT object',
#             #'      comp1.z: 0.0',
#             #'      comp2.derivative_exec_count: 0',
#             #'      comp2.exec_count: 2',
#             #'      comp2.itername: 1-comp2',
#             #'      comp2.z: 1.0',
#             #'      driver.workflow.itername: 1',
#             ]
#         #        print sout.getvalue()
#         expected = [
#             'Constants:',
#             '   comp1.b_bool: False',
#             '   comp1.directory: ',
#             '   comp1.force_fd: False',
#             '   comp1.missing_deriv_policy: error',
#             '   comp1.x: 0.0',
#             '   comp1.y: 0.0',
#             '   comp2.directory: ',
#             '   comp2.force_fd: False',
#             '   comp2.missing_deriv_policy: error',
#             '   directory: ',
#             '   driver.case_inputs.comp1.x_array_0_: [2.0]',
#             '   driver.case_inputs.comp1.x_array_1_: [2.0]',
#             '   driver.case_inputs.comp1.x_array_2_: [2.0]',
#             '   driver.directory: ',
#             '   driver.force_fd: False',
#             '   driver.gradient_options.atol: 1e-09',
#             '   driver.gradient_options.derivative_direction: auto',
#             '   driver.gradient_options.directional_fd: False',
#             '   driver.gradient_options.fd_blocks: []',
#             '   driver.gradient_options.fd_form: forward',
#             '   driver.gradient_options.fd_step: 1e-06',
#             '   driver.gradient_options.fd_step_type: absolute',
#             '   driver.gradient_options.force_fd: False',
#             '   driver.gradient_options.lin_solver: scipy_gmres',
#             '   driver.gradient_options.maxiter: 100',
#             '   driver.gradient_options.rtol: 1e-09',
#             '   force_fd: False',
#             '   missing_deriv_policy: assume_zero',
#             '   recording_options.excludes: []',
#             '   recording_options.includes: ["*""]',
#             '   recording_options.save_problem_formulation: True',
#             'Case:',
#             '   uuid: 2fe2830f-798c-11e4-800e-20c9d0478eff',
#             '   timestamp: 1417460373.374139',
#             '   inputs:',
#             '      comp1.x_array[0]: 2.0',
#             '      comp1.x_array[1]: 2.0',
#             '      comp1.x_array[2]: 2.0',
#             '   outputs:',
#             '      Response(comp1.a_array): [ 1.   3.   5.5]',
#             '      Response(comp1.vt): <openmdao.main.test.test_vartree.DumbVT object at 0x1131dbad0>',
#             '      comp1.derivative_exec_count: 0',
#             '      comp1.exec_count: 2',
#             '      comp1.itername: 1-comp1',
#             '      comp2.derivative_exec_count: 0',
#             '      comp2.exec_count: 2',
#             '      comp2.itername: 1-comp2',
#             '      driver.workflow.itername: 1',
#         ]
#         lines = sout.getvalue().split('\n')
#         for index, line in enumerate(lines):
#             if line.startswith('Case:'):
#                 for i in range(len(expected)):
#                     if expected[i].startswith('   uuid:'):
#                         self.assertTrue(lines[index+i].startswith('   uuid:'))
#                     elif expected[i].startswith('   timestamp:'):
#                         self.assertTrue(lines[index+i].startswith('   timestamp:'))
#                     elif expected[i].startswith('      Response(comp1.vt):') or \
#                          expected[i].startswith('      comp1.vt:'):
#                         self.assertTrue(lines[index+i].startswith(expected[i]))
#                     else:
#                         self.assertEqual(lines[index+i], expected[i])
#                 break
#         else:
#             self.fail("couldn't find the expected Case")



    #def test_flatten(self):
            ## create some Cases
    
            #self.top.recorders = [CSVCaseRecorder(filename=self.filename)]
            #self.top.recorders[0].num_backups = 0
            ##self.top.driver.add_parameter(['comp1.x', 'comp1.y'], low=-100, high=100)
            #self.top.driver.add_objective(['comp1.vt'])
            #self.top.run()
            #cases = [case for case in self.top.recorders[0].get_iterator()]
            #pass
    
    def test_CSVCaseRecorder_messages(self):
        rec = CSVCaseRecorder(filename=self.filename)
        rec.startup()
        rec.register(self, ['comp1.x', 'comp1.y', 'comp2.x'], [])
        rec.record(self, [2.0, 4.3, 1.9], [], None, '', '')
        try:
            rec.record(self, [2.0, 1.9], [], None, '', '')
        except Exception as err:
            self.assertEqual(str(err),
                             "number of data points (9) doesn't match"
                             " header size (10) in CSV recorder")
        else:
            self.fail("Exception expected")
        finally:
            rec.close()

        ## BAN - took this test out because only types with a flattener function
        ##       will be returned by the Case, so incompatible types just won't
        ##       be seen by the CSVCaseRecorder at all.  Need to discuss with
        ##       users (and Ken) to see if this is reasonable.
        #self.top.comp2.add('a_slot', Slot(object, iotype='in'))
        #self.top.recorders = [CSVCaseRecorder(filename=self.filename)]

        #case = Case(inputs=[('comp2.a_slot', None)])
        #try:
            #self.top.recorders[0].record(case)
        #except ValueError, err:
            #msg = "CSV format does not support variables of type <type 'NoneType'>"
            #self.top.recorders[0].close()
            #self.assertEqual(msg, str(err))
        #else:
            #self.top.recorders[0].close()
            #self.fail('ValueError Expected')

    def test_close(self):
        self.top.recorders = [CSVCaseRecorder(filename=self.filename)]
        self.top.recorders[0].num_backups = 0
        self.top.run()
        outputs = ['comp1.z', 'comp2.z', 'comp1.a_string',
                   'comp1.a_array[2]', 'driver.workflow.itername']
        inputs = ['comp1.x', 'comp1.y', 'comp1.x_array[1]', 'comp1.b_bool']
        self.top.recorders[0].register(self, inputs, outputs)
        outputs = [0, 0, 'world', 0, '1']
        inputs = [0.1, 2 + .1, 99.88, True]
        code = "self.top.recorders[0].record(self, inputs, outputs, None, '', '')"
        assert_raises(self, code, globals(), locals(), RuntimeError,
                      'Attempt to record on closed recorder')

    def test_csvbackup(self):

        # Cleanup from any past failures
        parts = self.filename.split('.')
        backups = glob.glob(''.join(parts[:-1]) + '_*')
        for item in backups:
            os.remove(item)

        self.top.recorders = [CSVCaseRecorder(filename=self.filename)]

        # Run twice, two backups.
        self.top.recorders[0].num_backups = 2
        self.top.run()
        # Granularity on timestamp is 1 second.
        time.sleep(1)
        self.top.run()
        backups = glob.glob(''.join(parts[:-1]) + '_*')
        self.assertEqual(len(backups), 2)

        # Set backups to 1 and rerun. Should delete down to 1 backup.
        self.top.recorders[0].num_backups = 1
        self.top.run()
        backups = glob.glob(''.join(parts[:-1]) + '_*')
        self.assertEqual(len(backups), 1)

        for item in backups:
            os.remove(item)
        backups = glob.glob(''.join(parts[:-1]) + '_*')

        self.top.recorders[0].num_backups = 0

    def test_iterate_twice(self):

        self.top.recorders = [CSVCaseRecorder(filename=self.filename)]
        self.top.recorders[0].num_backups = 0
        self.top.run()

        data = self.top.recorders[0].get_iterator()

        for case in data:
            keys1 = case.keys()

        for case in data:
            keys2 = case.keys()

        self.assertEqual(keys1, keys2)

    def test_save(self):
        # Check that a recorder can be saved to an egg.
        self.top.recorders = [CSVCaseRecorder(filename=self.filename)]
        self.top.recorders[0].num_backups = 0
        self.top.recorders[0].startup()
        try:
            self.top.save_to_egg('top', '1')
        finally:
            for name in glob.glob('top*.egg'):
                os.remove(name)


if __name__ == '__main__':
    unittest.main()
