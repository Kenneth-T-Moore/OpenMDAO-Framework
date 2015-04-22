
import numpy as np

from openmdao.util.testutil import assert_rel_error
from openmdao.main.api import Assembly, Component, set_as_top, Driver
from openmdao.main.datatypes.api import Float, Array
from openmdao.main.test.simpledriver import SimpleDriver
from openmdao.test.execcomp import ExecCompWithDerivatives, ExecComp

top = set_as_top(Assembly())

exp1 = ["y1 = 3.0*x", "y2 = 4.0*x"]
exp2 = ["y = -2.0*x"]
exp3 = ["y = 5.0*x"]

deriv1 = ["dy1_dx = 3.0", "dy2_dx = 4.0"]
deriv2 = ["dy_dx = -2.0"]
deriv3 = ["dy_dx = 5.0"]

top.add('comp1', ExecCompWithDerivatives(exp1, deriv1))
top.add('comp2', ExecCompWithDerivatives(exp2, deriv2))
top.add('comp3', ExecCompWithDerivatives(exp3, deriv3))
top.add('driver', SimpleDriver())

top.driver.workflow.add(['comp1', 'comp2', 'comp3'])
top.connect('comp1.y1', 'comp2.x')
top.connect('comp1.y2', 'comp3.x')
top.driver.add_parameter('comp1.x', low=-100, high=100)
top.driver.add_constraint('comp2.y < 1000')
top.driver.add_constraint('comp3.y < 1000')

top.driver.gradient_options.lin_solver = 'matmat'
top.run()

J = top.driver.calc_gradient(return_format='dict')


print '15, -8'
print J
