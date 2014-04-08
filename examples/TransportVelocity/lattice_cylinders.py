"""Incompressible flow past a periodic lattice of cylinders"""

# PyZoltan imports
from pyzoltan.core.carray import LongArray

# PySPH imports
from pysph.base.nnps import DomainLimits
from pysph.base.utils import get_particle_array
from pysph.base.kernels import Gaussian, WendlandQuintic, CubicSpline
from pysph.solver.solver import Solver
from pysph.solver.application import Application
from pysph.sph.integrator import TransportVelocityStep, Integrator

# the eqations
from pysph.sph.equation import Group
from pysph.sph.wc.basic import BodyForce
from pysph.sph.wc.transport_velocity import (ArtificialStress,
    DensitySummation, SolidWallBC, VolumeSummation, StateEquation,
    ContinuityEquation, MomentumEquation)

# numpy
import numpy as np

# domain and reference values
L = 0.1; Umax = 5e-5
c0 = 10 * Umax; rho0 = 1000.0
p0 = c0*c0*rho0
a = 0.02; H = L
fx = 1.5e-7

# Reynolds number and kinematic viscosity
Re = 1.0; nu = a*Umax/Re

# Numerical setup
nx = 100; dx = L/nx
ghost_extent = 5 * 1.5 * dx
hdx = 1.2

# adaptive time steps
h0 = hdx * dx
dt_cfl = 0.25 * h0/( c0 + Umax )
dt_viscous = 0.125 * h0**2/nu
dt_force = 0.25 * np.sqrt(h0/abs(fx))

tf = 100.0
dt = 0.5 * min(dt_cfl, dt_viscous, dt_force)

def create_particles(**kwargs):
    # create all the particles
    _x = np.arange( dx/2, L, dx )
    _y = np.arange( dx/2, H, dx)
    x, y = np.meshgrid(_x, _y); x = x.ravel(); y = y.ravel()

    # sort out the fluid and the solid
    indices = []
    cx = 0.5 * L; cy = 0.5 * H
    for i in range(x.size):
        xi = x[i]; yi = y[i]
        if ( np.sqrt( (xi-cx)**2 + (yi-cy)**2 ) > a ):
                #if ( (yi > 0) and (yi < H) ):
            indices.append(i)

    to_extract = LongArray(len(indices)); to_extract.set_data(np.array(indices))

    # create the arrays
    solid = get_particle_array(name='solid', x=x, y=y)

    # remove the fluid particles from the solid
    fluid = solid.extract_particles(to_extract); fluid.set_name('fluid')
    solid.remove_particles(to_extract)
    
    print "Periodic cylinders :: Re = %g, nfluid = %d, nsolid=%d, dt = %g"%(
        Re, fluid.get_number_of_particles(),
        solid.get_number_of_particles(), dt)
    
    # add requisite properties to the arrays:
    # particle volume
    fluid.add_property( {'name': 'V'} )
    solid.add_property( {'name': 'V'} )

    # advection velocities and accelerations
    fluid.add_property( {'name': 'uhat'} )
    fluid.add_property( {'name': 'vhat'} )

    fluid.add_property( {'name': 'auhat'} )
    fluid.add_property( {'name': 'avhat'} )

    fluid.add_property( {'name': 'au'} )
    fluid.add_property( {'name': 'av'} )
    fluid.add_property( {'name': 'aw'} )

    # kernel summation correction for the solid
    solid.add_property( {'name': 'wij'} )

    # imopsed velocity on the solid
    solid.add_property( {'name': 'u0'} )
    solid.add_property( {'name': 'v0'} )

    # density acceleration
    fluid.add_property( {'name':'arho'} )

    # magnitude of velocity
    fluid.add_property({'name':'vmag'})

    # setup the particle properties
    volume = dx * dx

    # mass is set to get the reference density of rho0
    fluid.m[:] = volume * rho0
    solid.m[:] = volume * rho0
    solid.rho[:] = rho0

    # reference pressures and densities
    fluid.rho[:] = rho0

    # volume is set as dx^2
    fluid.V[:] = 1./volume
    solid.V[:] = 1./volume

    # smoothing lengths
    fluid.h[:] = hdx * dx
    solid.h[:] = hdx * dx

    # return the particle list
    return [fluid, solid]

# domain for periodicity
domain = DomainLimits(
    xmin=0, xmax=L, ymin=0, ymax=H, periodic_in_x=True,periodic_in_y=True)

# Create the application.
app = Application(domain=domain)

# Create the kernel
kernel = Gaussian(dim=2)

integrator = Integrator(fluid=TransportVelocityStep())

# Create a solver.
solver = Solver(kernel=kernel, dim=2, integrator=integrator)

# Setup default parameters.
solver.set_time_step(dt)
solver.set_final_time(tf)

equations = [

    # State equation
    Group(
        equations=[
            DensitySummation(dest='fluid', sources=['fluid','solid']),
            #VolumeSummation(dest='fluid',sources=['fluid', 'solid'],),

            ]),

    # solid wall bc
    Group(
        equations=[

            SolidWallBC(dest='solid', sources=['fluid'], gx=fx, rho0=rho0, p0=p0),
            #SolidWallBC(dest='solid', sources=['fluid',], gx=fx, b=0.0),

            ]),

    # accelerations
    Group(
        equations=[
            StateEquation(dest='fluid', sources=None, b=1.0, rho0=rho0, p0=p0),
            BodyForce(dest='fluid', sources=None, fx=fx),
            MomentumEquation(dest='fluid', sources=['fluid', 'solid'], nu=nu),
            ArtificialStress(dest='fluid', sources=['fluid',])

            # BodyForce(dest='fluid', sources=None, fx=fx),
            # MomentumEquation(dest='fluid', sources=['fluid', 'solid'], nu=nu),
            # ContinuityEquation(dest='fluid', sources=['fluid', 'solid']),

            ]),
    ]

# Setup the application and solver.  This also generates the particles.
app.setup(solver=solver, equations=equations,
          particle_factory=create_particles)

app.run()
