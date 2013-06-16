"""Poiseuille flow using the transport velocity formulation of Adami et.al."""

# PyZoltan imports
from pyzoltan.core.carray import LongArray

# PySPH imports
from pysph.base.nnps import DomainLimits
from pysph.base.utils import get_particle_array
from pysph.base.kernels import Gaussian, WendlandQuintic, CubicSpline
from pysph.solver.solver import Solver
from pysph.solver.application import Application
from pysph.sph.integrator import TransportVelocityIntegrator

# the eqations
from pysph.sph.equations import Group
from pysph.sph.equations import BodyForce
from pysph.sph.transport_velocity_equations import TransportVelocitySummationDensity,\
    TransportVelocitySolidWall, TransportVelocityMomentumEquation

# numpy
import numpy as np

# domain and reference values
Re = 0.0125
d = 0.5; Ly = 2*d; Lx = 0.4*Ly
rho0 = 1.0; nu = 1.0
Vmax = nu*Re/(2*d)
c0 = 10*Vmax; p0 = c0*c0/rho0

# The body force is adjusted to give the Required Reynold's number
# based on the steady state maximum velocity Vmax:
# Vmax = fx/(2*nu)*(d^2) at the centerline
fx = Vmax * 2*nu/rho0/(d**2)

# Numerical setup
dx = 0.05
ghost_extent = 5 * dx
hdx = 1.2

def create_particles(empty=False, **kwargs):
    if empty:
        fluid = get_particle_array(name='fluid')
        channel = get_particle_array(name='channel')
    else:
        _x = np.arange( dx/2, Lx, dx )

        # create the fluid particles
        _y = np.arange( dx/2, Ly, dx )

        x, y = np.meshgrid(_x, _y); fx = x.ravel(); fy = y.ravel()

        # create the channel particles at the top
        _y = np.arange(Ly+dx/2, Ly+dx/2+ghost_extent, dx)
        x, y = np.meshgrid(_x, _y); tx = x.ravel(); ty = y.ravel()

        # create the channel particles at the bottom
        _y = np.arange(-dx/2, -dx/2-ghost_extent, -dx)
        x, y = np.meshgrid(_x, _y); bx = x.ravel(); by = y.ravel()
        
        # concatenate the top and bottom arrays
        cx = np.concatenate( (tx, bx) )
        cy = np.concatenate( (ty, by) )

        # create the arrays
        channel = get_particle_array(name='channel', x=cx, y=cy)
        fluid = get_particle_array(name='fluid', x=fx, y=fy)

        print "Poiseuille flow :: Re = %g, nfluid = %d, nchannel=%d"%(
            Re, fluid.get_number_of_particles(),
            channel.get_number_of_particles())

    # add requisite properties to the arrays:
    # particle volume
    fluid.add_property( {'name': 'V'} )
    channel.add_property( {'name': 'V'} )
        
    # advection velocities and accelerations
    fluid.add_property( {'name': 'uhat'} )
    fluid.add_property( {'name': 'vhat'} )

    channel.add_property( {'name': 'uhat'} )
    channel.add_property( {'name': 'vhat'} )

    fluid.add_property( {'name': 'auhat'} )
    fluid.add_property( {'name': 'avhat'} )

    fluid.add_property( {'name': 'au'} )
    fluid.add_property( {'name': 'av'} )
    fluid.add_property( {'name': 'aw'} )
    
    # kernel summation correction for the channel
    channel.add_property( {'name': 'wij'} )

    # imopsed velocity on the channel
    channel.add_property( {'name': 'u0'} )
    channel.add_property( {'name': 'v0'} )                         
        
    # setup the particle properties
    if not empty:
        volume = dx * dx

        # mass is set to get the reference density of rho0
        fluid.m[:] = volume * rho0
        channel.m[:] = volume * rho0

        # volume is set as dx^2
        fluid.V[:] = 1./volume
        channel.V[:] = 1./volume

        # smoothing lengths
        fluid.h[:] = hdx * dx
        channel.h[:] = hdx * dx
        
        # zero external velocity
        channel.u0[:] = 0.0
        channel.v0[:] = 0.0
                
    # return the particle list
    return [fluid, channel]

# domain for periodicity
domain = DomainLimits(xmin=0, xmax=Lx, periodic_in_x=True)

# Create the application.
app = Application(domain=domain)

# Create the kernel
kernel = WendlandQuintic(dim=2)

print domain, kernel

# Create a solver.
solver = Solver(
    kernel=kernel, dim=2, integrator_type=TransportVelocityIntegrator)

# Setup default parameters.
solver.set_time_step(1e-5)
solver.set_final_time(2.0)

equations = [

    # Summation density for the fluid phase
    Group(
        equations=[
            TransportVelocitySummationDensity(
                dest='fluid', sources=['fluid','channel'], rho0=rho0, c0=c0),
            ]),
    
    # boundary conditions for the channel wall
    Group(
        equations=[
            TransportVelocitySolidWall(
                dest='channel', sources=['fluid',], rho0=rho0, p0=p0),
            ]),
    
    # acceleration equation
    Group(
        equations=[
            BodyForce(dest='fluid', sources=None, fx=fx),

            TransportVelocityMomentumEquation(
                dest='fluid', sources=['fluid', 'channel'], nu=nu, pb=p0)
            ]),
    ]

# Setup the application and solver.  This also generates the particles.
app.setup(solver=solver, equations=equations, 
          particle_factory=create_particles)

with open('poiseuille.pyx', 'w') as f:
    app.dump_code(f)

app.run()
