"""
JSON/BSON Case Recording.
"""

import cStringIO
import StringIO
import logging
import sys
import time
import os
import inspect

from numpy  import ndarray
from struct import pack
from uuid   import uuid1

from openmdao.main.api import VariableTree
from openmdao.main.interfaces import implements, ICaseRecorder
from openmdao.main.releaseinfo import __version__
from openmdao.util.typegroups import real_types


import h5py
import numpy as np

from openmdao.main.mpiwrap import MPI

#from mpi4py import MPI


def write_to_hdf5( group, name, value ):


    if MPI:
        rank = MPI.COMM_WORLD.rank
    else:  
        rank = 0

    if isinstance(value,dict):
        print 'write_to_hdf5 dict', rank, name, value
        dict_grp = group[name]
        for k, v in value.items():
            write_to_hdf5( dict_grp, k, v )
    # elif isinstance( value, VariableTree): TODO
    #     print 'create VariableTree', name, MPI.COMM_WORLD.rank
    #     vartree_grp = group.create_group(name)
    #     #QQQQQvartree_grp.attrs['__vartree__'] = True
    #     for k in value.list_vars():
    #         write_to_hdf5( vartree_grp, k, value.get(k) )
    elif isinstance( value, np.ndarray):
        print 'write_to_hdf5 np.ndarray', rank, name, value
        dset = group[name] 
        dset[:] = value[:]
    elif isinstance( value, list):
        if len( value ) > 0:
            if isinstance( value[0], str):
                print 'write_to_hdf5 str list', rank, name, value
                dset = group[name] 
                for i,v in enumerate(value): # TODO there must be a better way
                    dset[i] = value[i]
        else:
            print 'write_to_hdf5 unknown list', rank, name, value
            # TODO How do we handle empty lists? Do not know type
    elif value == None :
        print 'write_to_hdf5 None',  name, value
        #group.attrs[name] = np.array([]) # TODO really need to write None here
        pass
    elif isinstance( value, np.float64):
        print 'write_to_hdf5 np.float64', rank, name, value
        dset = group[name] 
        dset[0,] = value
    elif isinstance(value,float):
        print 'write_to_hdf5 float', rank, name, value
        dset = group[name] 
        dset[0,] = value
    elif isinstance(value,int):
        print 'write_to_hdf5 int', rank, name, value
        dset = group[name] 
        dset[0,] = value
    elif isinstance(value,str):
        print 'write_to_hdf5 string', rank, name, value
        dset = group[name] 
        dset[0,] = value
    elif isinstance(value,bool):
        print 'write_to_hdf5 bool', rank, name, value
        dset = group[name] 
        dset[0,] = value


def write_groups_to_hdf5( group, name, value ):

    if MPI:
        rank = MPI.COMM_WORLD.rank
    else:  
        rank = 0

    if isinstance(value,dict):
        print 'write_groups_to_hdf5 dict', rank, name, value
        dict_grp = group.create_group(name)
        #dict_grp.attrs['__dict__'] = True # To indicate that this HDF5 group represents an actual Python dict
        for k, v in value.items():
            write_groups_to_hdf5( dict_grp, k, v )
    # elif isinstance( value, VariableTree): # TODO
    #     print 'create VariableTree', name, MPI.COMM_WORLD.rank
    #     vartree_grp = group.create_group(name)
    #     #QQQQQvartree_grp.attrs['__vartree__'] = True
    #     for k in value.list_vars():
    #         write_to_hdf5( vartree_grp, k, value.get(k) )
    elif isinstance( value, np.ndarray):
        print 'write_groups_to_hdf5 np.ndarray', rank, name, value
        group.create_dataset(name, data=value)
    elif isinstance( value, list):
        if len( value ) > 0:
            if isinstance( value[0], str):
                print 'write_groups_to_hdf5 str list', rank, name, value
                group.create_dataset(name, (len(value),1),'S50' ) # TODO use variable length strings
        else:
            print 'write_groups_to_hdf5 unknown list', rank, name, value
            group.create_dataset(name,(0,)) # TODO How do we handle empty lists? Do not know type
    elif value == None :
        print 'write_groups_to_hdf5 None', rank, name, value
        group.create_dataset(name,(0,))
    elif isinstance( value, np.float64):
        print 'write_groups_to_hdf5 np.float64', rank, name, value
        group.create_dataset(name, (1,), dtype='f')
    elif isinstance(value,float):
        print 'write_groups_to_hdf5 float', rank, name, value
        group.create_dataset(name, (1,), dtype='f')
    elif isinstance(value,int):
        print 'write_groups_to_hdf5 int', rank, name, value
        group.create_dataset(name, (1,), dtype='i')
    elif isinstance(value,str):
        print 'write_groups_to_hdf5 string', rank, name, value
        #dt = h5py.special_dtype(vlen=bytes)
        dset = group.create_dataset(name, (1,), dtype="S50")
    elif isinstance(value,bool):
        print 'write_groups_to_hdf5 bool', rank, name, value
        dset = group.create_dataset(name, (1,), dtype=np.bool)


























class HDF5CaseRecorder(object):
    """
    Dumps a run in HDF5 form to `out`, which may be a string or a file-like
    object (defaults to ``stdout``). If `out` is ``stdout`` or ``stderr``,
    then that standard stream is used. Otherwise, if `out` is a string, then
    a file with that name will be opened in the current directory.
    If `out` is None, cases will be ignored.
    """

    implements(ICaseRecorder)

    def __init__(self, out='cases.hdf5', indent=4, sort_keys=True):
        self._cfg_map = {}
        self._uuid = None
        self._cases = None

        # not used yet but for getting values of variables
        #     from subcases
        self._last_child_case_uuids = {} # keyed by driver id

        #self.hdf5_main_file_object = h5py.File(out, "w", driver='mpio', comm=MPI.COMM_WORLD)

        if MPI:
            print 'type(MPI.COMM_WORLD)', type(MPI.COMM_WORLD)

        # if not MPI or MPI.COMM_WORLD.rank == 0 : # TODO only rank 0 process needs to write the primary case recording file
        #     print "create hdf5_main_file_object"
        #     self.hdf5_main_file_object = h5py.File(out, "w")
        #     print "done creating hdf5_main_file_object"

        self.hdf5_main_file_object = h5py.File(out, "w", driver='mpio', comm=MPI.COMM_WORLD)


        self.hdf5_case_record_file_objects = {}

        self.case_recording_filenames = {}

        if MPI:
            print 'COMM_WORLD', MPI.COMM_WORLD

        #self.hdf5_main_file_object.atomic = True 

        self.indent = indent
        self.sort_keys = sort_keys
        self._count = 0

    def startup(self):
        """ Prepare for new run. """
        pass

    #def register(self, driver, inputs, outputs,inputs_all_processes, outputs_all_processes):
    def register(self, driver, inputs, outputs):
        """ Register names for later record call from `driver`. """

        # If this driver is not running on this process, do not bother registering
        # if not driver._system.is_active():    ########### TODO 
        #     return

        #import pdb; pdb.set_trace()
        self._cfg_map[driver] = (inputs, outputs)
        #self._cfg_map[driver] = (inputs_all_processes, outputs_all_processes)

        #self.inputs_all_processes = inputs_all_processes
        #self.outputs_all_processes = outputs_all_processes
        scope = driver.parent
        prefix = scope.get_pathname()

        # print 'check if seg3.driver.directory local', driver.workflow._system.is_variable_local( 'seg3.driver.directory' )
        #print 'check if seg3.driver.itername local', driver.get_pathname(), driver.workflow._system.is_variable_local( 'seg3.driver.itername`' ), MPI.COMM_WORLD.rank
        # print 'check if s3 local', driver.workflow._system.is_variable_local( 's3' )

        print 'driver.get_pathname()', driver.get_pathname()

        print 'driver.workflow._system', driver.workflow._system
        print 'driver.workflow._system.subsystems()', driver.workflow._system.subsystems()

        if MPI:
            print 'isactive: driver, rank, active', driver.get_pathname(), MPI.COMM_WORLD.rank, driver._system.is_active()

        # from openmdao.main.systems import SerialSystem, ParallelSystem
        # communicator = None
        # for ss in driver.workflow._system.subsystems():
        #     if isinstance( ss, ParallelSystem):
        #         print 'ParallelSystem comm', ss.mpi.comm
        #         communicator = ss.mpi.comm

        print "for driver, in workflow", prefix + "."+driver.name, ",".join([c.name for c in driver.workflow])
        print "for driver, recording", prefix + "."+driver.name, ",".join(inputs+outputs)

        if MPI:
            print 'register driver, drivername, rank, system, prefix', driver, driver.name, MPI.COMM_WORLD.rank, driver.workflow._system, prefix
        #self.hdf5_file_objects[driver] = h5py.File('cases_%s_%s.hdf5' % (prefix, driver.name), "w", driver='mpio', comm=MPI.COMM_WORLD)

        case_recording_filename = 'cases_%s_%s.hdf5' % (prefix, driver.name)
        print 'opening HDF5 file', case_recording_filename

        if not driver._system.is_active():    ########### TODO 
            return

        ##########   restore   
        if driver.workflow._system.get_req_cpus() > 1: 
            communicator = driver.workflow._system.mpi.comm # Recommened by Bret. check to see if None, MPI.COMM_NULL
            print 'driver is  parallel', driver.get_pathname(), communicator, driver.workflow._system.get_req_cpus()
            self.hdf5_case_record_file_objects[driver] = h5py.File(case_recording_filename, "w",driver='mpio', comm=communicator)
        else:
            print 'driver is not parallel', driver.get_pathname()
            self.hdf5_case_record_file_objects[driver] = h5py.File(case_recording_filename, "w")

        self.case_recording_filenames[driver.get_pathname()] = case_recording_filename



    def record_constants(self, constants):
        """ Record constant data. """

        print 'in record_constants before if', MPI.COMM_WORLD.rank

        # # TODO only rank 0 needs to do this
        # if MPI and not MPI.COMM_WORLD.rank == 0 :
        #     return 

        print 'in record_constants after if', MPI.COMM_WORLD.rank

        info = self.get_simulation_info(constants)

        simulation_info_grp = self.hdf5_main_file_object.create_group("simulation_info")
        
        ##### Just create group structure on all processes using the merged JSON info ######

        write_groups_to_hdf5( simulation_info_grp, 'OpenMDAO_Version', info['OpenMDAO_Version'])
        write_groups_to_hdf5( simulation_info_grp, 'comp_graph', info['comp_graph'])
        write_groups_to_hdf5( simulation_info_grp, 'graph', info['graph'])
        write_groups_to_hdf5( simulation_info_grp, 'uuid', info['uuid'])
        write_groups_to_hdf5( simulation_info_grp, 'name', info['name'])
       
        constants_grp = simulation_info_grp.create_group("constants")
        for k,v in info['constants'].items():
            write_groups_to_hdf5( constants_grp, k, v )

        expressions_grp = simulation_info_grp.create_group("expressions")
        for k,v in info['expressions'].items():
           write_groups_to_hdf5( expressions_grp, k, v )
            
        variable_metadata_grp = simulation_info_grp.create_group("variable_metadata")
        for k,v in info['variable_metadata'].items():
            write_groups_to_hdf5( variable_metadata_grp, k, v )

        ##### Write the datasets using only the data available to this process ######

        write_to_hdf5( simulation_info_grp, 'OpenMDAO_Version', info['OpenMDAO_Version'])
        write_to_hdf5( simulation_info_grp, 'comp_graph', info['comp_graph'])
        write_to_hdf5( simulation_info_grp, 'graph', info['graph'])
        write_to_hdf5( simulation_info_grp, 'uuid', info['uuid'])
        write_to_hdf5( simulation_info_grp, 'name', info['name'])
       
        for k,v in info['constants'].items():
            write_to_hdf5( constants_grp, k, v )

        for k,v in info['expressions'].items():
           write_to_hdf5( expressions_grp, k, v )
            
        for k,v in info['variable_metadata'].items():
            write_to_hdf5( variable_metadata_grp, k, v )


        ##### Just create group structure on all processes using the merged JSON info ######
        for i, info in enumerate(self.get_driver_info()):
            driver_info_name = 'driver_info_%s' % (i+1)
            #import pdb; pdb.set_trace()
            driver_info_group = self.hdf5_main_file_object.create_group(driver_info_name)
            for k,v in info.items():
                print 'driver key', k, v
                write_groups_to_hdf5( driver_info_group, k, v )
                write_to_hdf5( driver_info_group, k, v ) # TODO really only rank 0 should do this

        ##### Write the datasets using only the data available to this process ######
        # for i, info in enumerate(self.get_driver_info()):
        #     # import pprint 
        #     # pprint.pprint( info )
        #     driver_info_name = 'driver_info_%s' % (i+1)
        #     for k,v in info.items():
        #         write_to_hdf5( driver_info_group, k, v )

        print 'in record_constants at end', MPI.COMM_WORLD.rank


    def record(self, driver, inputs, outputs, exc, case_uuid, parent_uuid):
        """ Dump the given run data. """






        print 'start of record', MPI.COMM_WORLD.rank

        if MPI:
            rank = MPI.COMM_WORLD.rank
        else:  
            rank = 0

        info = self.get_case_info(driver, inputs, outputs, exc,
                                  case_uuid, parent_uuid)
        self._cases += 1
        iteration_case_name = 'iteration_case_%s' % self._cases

        #print "iteration_case_name", iteration_case_name


        hdf5_file_object = self.hdf5_case_record_file_objects[driver]

        print 'writing records to file from rank', driver.get_pathname(), hdf5_file_object.filename, iteration_case_name, rank

        ##### Just create group structure on all processes using the merged JSON info ######
        self._count += 1
        iteration_case_group = hdf5_file_object.create_group(iteration_case_name)
        for k,v in info.items():
            print 'record case make group', rank, iteration_case_group.name, k, v
            write_groups_to_hdf5( iteration_case_group, k, v ) 

        #return


        scope = driver.parent
        prefix = scope.get_pathname()
        print 'prefix', prefix, len(prefix)

        ##### Write the datasets using only the data available to this process ######
        for k,v in info.items():
            print 'record case set values', rank, k 
            if k != 'data':
                write_to_hdf5( iteration_case_group, k, v )
            else:
                print 'writing data'
                print 'write_to_hdf5 dict', rank, k
                data_grp = iteration_case_group[k]
                for name,value in v.items():

                    if name.endswith( '.out0'):
                        name_for_local_check = name[:-len('.out0')]
                    else:
                        name_for_local_check = name
                    if prefix:
                        name_for_local_check = name_for_local_check[ len(prefix) + 1 : ] 

                    # if name_for_local_check == 'pseudo_3':
                    #     import pdb; pdb.set_trace()
                    print 'is_variable_local', name, name_for_local_check
                    #if driver.workflow._system.is_variable_local( name_for_local_check ):
                    #if driver.workflow._system.is_variable_local( name_for_local_check ): # TODO should cache these. No need to call for each record
                    if driver.workflow._system.is_variable_local( name_for_local_check ): # TODO should cache these. No need to call for each record
                        print "islocal true", name_for_local_check, rank, name
                        print 'actual write to hdf5 file', name, hdf5_file_object.filename, rank
                        write_to_hdf5( data_grp, name, value )
                        hdf5_file_object.flush()
                        print 'whatisin', hdf5_file_object.filename, hdf5_file_object.keys()
                    else:
                        print "islocal false", rank, hdf5_file_object.filename, name

        print 'end of record', MPI.COMM_WORLD.rank



    def close(self):
        """
        Closes `out` unless it's ``sys.stdout`` or ``sys.stderr``.
        Note that a closed recorder will do nothing in :meth:`record`.
        """

        print "in close", MPI.COMM_WORLD.rank


        MPI.COMM_WORLD.Barrier()

        if 1 or not MPI or MPI.COMM_WORLD.rank == 0 : # only rank 0 process needs to write the primary case recording file

            print "closing hdf5_main_file_object"
            sys.stdout.flush()


            ################# restore
            # # add the individual case recording files to the main hdf5 file
            # iteration_case_grp = self.hdf5_main_file_object.create_group("iteration_cases")

            # for driver_path, filename in self.case_recording_filenames.items():
            #     # Create an external link to the root group "/" in the driver specific iteration cases 
            #     # B['External'] = h5py.ExternalLink("dset.h5", "/dset")
            #     iteration_case_grp[driver_path] = h5py.ExternalLink(filename, "/")

            print "close hdf5_case_recorder"
            self.hdf5_main_file_object.close()


        ###################### restore
        # TODO should really only close the ones that belong to this process
        for hdf5_case_record_file in self.hdf5_case_record_file_objects.values() :
            print 'whatisin at close', hdf5_case_record_file.filename, hdf5_case_record_file.keys(), MPI.COMM_WORLD.rank
            hdf5_case_record_file.close()            

        # if self.out is not None and self._cases is not None:
        #     self.out.write('}\n')

        # if self.out not in (None, sys.stdout, sys.stderr):
        #     if not isinstance(self.out,
        #                       (StringIO.StringIO, cStringIO.OutputType)):
        #         # Closing a StringIO deletes its contents.
        #         self.out.close()
        #     self.out = None

        self._cases = None

































    def get_simulation_info(self, constants):
        """ Return simulation info dictionary. """
        # Locate top level assembly from first driver registered.
        top = self._cfg_map.keys()[0].parent
        while top.parent:
            top = top.parent
        #prefix_drop = len(top.name)+1 if top.name else 0
        prefix_drop = 0

        # Collect variable metadata.
        cruft = ('desc', 'framework_var', 'type', 'validation_trait')
        variable_metadata = {}
        for driver, (ins, outs) in self._cfg_map.items():
            scope = driver.parent
            prefix = '' if scope is top else scope.get_pathname()[prefix_drop:]
            if prefix:
                prefix += '.'

            for name in ins + outs:
                if '_pseudo_' in name or name.endswith('.workflow.itername'):
                    pass  # No metadata.
                else:
                    name, _, rest = name.partition('[')
                    try:
                        metadata = scope.get_metadata(name)
                    except AttributeError:
                        pass  # Error already logged.
                    else:
                        metadata = metadata.copy()
                        for key in cruft:
                            if key in metadata:
                                del metadata[key]
                        variable_metadata[prefix+name] = metadata

        for name in constants:
            name, _, rest = name.partition('[')
            metadata = top.get_metadata(name).copy()
            for key in cruft:
                if key in metadata:
                    del metadata[key]
            variable_metadata[name] = metadata

        # Collect expression data.
        expressions = {}
        for driver, (ins, outs) in sorted(self._cfg_map.items(),
                                          key=lambda item: item[1][0]):
            scope = driver.parent
            prefix = '' if scope is top else scope.get_pathname()[prefix_drop:]
            if prefix:
                prefix += '.'

            if hasattr(driver, 'eval_objectives'):
                for obj in driver.get_objectives().values():
                    info = dict(data_type='Objective',
                                pcomp_name=prefix+obj.pcomp_name)
                    expressions[prefix+str(obj)] = info

            if hasattr(driver, 'eval_responses'):
                for response in driver.get_responses().values():
                    info = dict(data_type='Response',
                                pcomp_name=prefix+response.pcomp_name)
                    expressions[prefix+str(response)] = info

            constraints = []
            if hasattr(driver, 'get_eq_constraints'):
                constraints.extend(driver.get_eq_constraints().values())
            if hasattr(driver, 'get_ineq_constraints'):
                constraints.extend(driver.get_ineq_constraints().values())
            for con in constraints:
                info = dict(data_type='Constraint',
                            pcomp_name=prefix+con.pcomp_name)
                expressions[prefix+str(con)] = info

        self._uuid = str(uuid1())
        self._cases = 0

        dep_graph = top.get_graph(format='json')
        comp_graph = top.get_graph(components_only=True, format='json')

        return dict(variable_metadata=variable_metadata,
                    expressions=expressions,
                    constants=constants,
                    graph=dep_graph,
                    comp_graph=comp_graph,
                    name=top.name,
                    OpenMDAO_Version=__version__,
                    uuid=self._uuid)

    def get_driver_info(self):
        """ Return list of driver info dictionaries. """

        # Locate top level assembly from first driver registered.
        top = self._cfg_map.keys()[0].parent
        while top.parent:
            top = top.parent
        #prefix_drop = len(top.name) + 1 if top.name else 0
        prefix_drop = 0

        driver_info = []
        for driver, (ins, outs) in sorted(self._cfg_map.items(),
                                          key=lambda item: item[0].get_pathname()):
            name = driver.get_pathname()[prefix_drop:]
            info = dict(name=name, _id=id(driver), recording=ins+outs)
            if hasattr(driver, 'get_parameters'):
                info['parameters'] = \
                    [str(param) for param in driver.get_parameters().values()]
            if hasattr(driver, 'eval_objectives'):
                info['objectives'] = \
                    [key for key in driver.get_objectives()]
            if hasattr(driver, 'eval_responses'):
                info['responses'] = \
                    [key for key in driver.get_responses()]
            if hasattr(driver, 'get_eq_constraints'):
                info['eq_constraints'] = \
                    [str(con) for con in driver.get_eq_constraints().values()]
            if hasattr(driver, 'get_ineq_constraints'):
                info['ineq_constraints'] = \
                    [str(con) for con in driver.get_ineq_constraints().values()]
            driver_info.append(info)
        return driver_info

    def get_case_info(self, driver, inputs, outputs, exc,
                      case_uuid, parent_uuid):
        """ Return case info dictionary. """
        in_names, out_names = self._cfg_map[driver]

        #import pdb; pdb.set_trace()

        scope = driver.parent
        prefix = scope.get_pathname()
        if prefix:
            prefix += '.'
        in_names = [prefix+name for name in in_names]
        out_names = [prefix+name for name in out_names]

        data = dict(zip(in_names, inputs))
        data.update(zip(out_names, outputs))

        #subdriver_last_case_uuids = {}
        #for subdriver in driver.subdrivers():
            #subdriver_last_case_uuids[ id(subdriver) ] = self._last_child_case_uuids[ id(subdriver) ]
        #self._last_child_case_uuids[ id(driver) ] = case_uuid


        return dict(_id=case_uuid,
                    _parent_id=parent_uuid or self._uuid,
                    _driver_id=id(driver),
                    #subdriver_last_case_uuids = subdriver_last_case_uuids,
                    error_status=None,
                    error_message=str(exc) if exc else '',
                    timestamp=time.time(),
                    data=data)

    def get_iterator(self):
        """ Just returns None. """
        return None


