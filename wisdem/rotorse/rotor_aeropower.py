#!/usr/bin/env python
# encoding: utf-8
"""
rotor.py

Created by Andrew Ning on 2012-02-28.
Copyright (c)  NREL. All rights reserved.
"""

from __future__ import print_function
import numpy as np
import os
from openmdao.api import IndepVarComp, ExplicitComponent, Group, Problem
from scipy.optimize import minimize_scalar, minimize
from scipy.interpolate import PchipInterpolator

from wisdem.ccblade.ccblade_component import CCBladeGeometry, CCBladePower
from wisdem.ccblade import CCAirfoil, CCBlade

from wisdem.commonse.distribution import RayleighCDF, WeibullWithMeanCDF
from wisdem.commonse.utilities import vstack, trapz_deriv, linspace_with_deriv, smooth_min, smooth_abs
from wisdem.commonse.environment import PowerWind
from wisdem.commonse.akima import Akima
from wisdem.rotorse.rotor_geometry import RotorGeometry, NREL5MW, DTU10MW, TUM3_35MW

from wisdem.rotorse import RPM2RS, RS2RPM

import time
# ---------------------
# Components
# ---------------------

# class MaxTipSpeed(ExplicitComponent):

#     R = Float(iotype='in', units='m', desc='rotor radius')
#     Vtip_max = Float(iotype='in', units='m/s', desc='maximum tip speed')

#     Omega_max = Float(iotype='out', units='rpm', desc='maximum rotation speed')

#     def execute(self):

#         self.Omega_max = self.Vtip_max/self.R * RS2RPM


#     def list_deriv_vars(self):

#         inputs = ('R', 'Vtip_max')
#         outputs = ('Omega_max',)

#         return inputs, outputs


#     def provideJ(self):

#         J = np.array([[-self.Vtip_max/self.R**2*RS2RPM, RS2RPM/self.R]])

#         return J


# class RegulatedPowerCurve(ExplicitComponent): # Implicit COMPONENT

#     def setup(self, naero, n_pc, n_pc_spline, regulation_reg_II5 = True, regulation_reg_III = True):

#         # parameters
#         self.add_input('control_Vin',        val=0.0, units='m/s',  desc='cut-in wind speed')
#         self.add_input('control_Vout',       val=0.0, units='m/s',  desc='cut-out wind speed')
#         self.add_input('control_ratedPower', val=0.0, units='W',    desc='electrical rated power')
#         self.add_input('control_minOmega',   val=0.0, units='rpm',  desc='minimum allowed rotor rotation speed')
#         self.add_input('control_maxOmega',   val=0.0, units='rpm',  desc='maximum allowed rotor rotation speed')
#         self.add_input('control_maxTS',      val=0.0, units='m/s',  desc='maximum allowed blade tip speed')
#         self.add_input('control_tsr',        val=0.0,               desc='tip-speed ratio in Region 2 (should be optimized externally)')
#         self.add_input('control_pitch',      val=0.0, units='deg',  desc='pitch angle in region 2 (and region 3 for fixed pitch machines)')
#         self.add_discrete_input('drivetrainType',     val='GEARED')
#         self.add_input('drivetrainEff',     val=0.0,               desc='overwrite drivetrain model with a given efficiency, used for FAST analysis')
        
#         self.add_input('r',         val=np.zeros(naero), units='m',   desc='radial locations where blade is defined (should be increasing and not go all the way to hub or tip)')
#         self.add_input('chord',     val=np.zeros(naero), units='m',   desc='chord length at each section')
#         self.add_input('theta',     val=np.zeros(naero), units='deg', desc='twist angle at each section (positive decreases angle of attack)')
#         self.add_input('Rhub',      val=0.0,             units='m',   desc='hub radius')
#         self.add_input('Rtip',      val=0.0,             units='m',   desc='tip radius')
#         self.add_input('hubHt',     val=0.0,             units='m',   desc='hub height')
#         self.add_input('precone',   val=0.0,             units='deg', desc='precone angle', )
#         self.add_input('tilt',      val=0.0,             units='deg', desc='shaft tilt', )
#         self.add_input('yaw',       val=0.0,             units='deg', desc='yaw error', )
#         self.add_input('precurve',      val=np.zeros(naero),    units='m', desc='precurve at each section')
#         self.add_input('precurveTip',   val=0.0,                units='m', desc='precurve at tip')

#         self.add_discrete_input('airfoils',  val=[0]*naero,                      desc='CCAirfoil instances')
#         self.add_discrete_input('B',         val=0,                              desc='number of blades')
#         self.add_input('rho',       val=0.0,        units='kg/m**3',    desc='density of air')
#         self.add_input('mu',        val=0.0,        units='kg/(m*s)',   desc='dynamic viscosity of air')
#         self.add_input('shearExp',  val=0.0,                            desc='shear exponent')
#         self.add_discrete_input('nSector',   val=4,                              desc='number of sectors to divide rotor face into in computing thrust and power')
#         self.add_discrete_input('tiploss',   val=True,                           desc='include Prandtl tip loss model')
#         self.add_discrete_input('hubloss',   val=True,                           desc='include Prandtl hub loss model')
#         self.add_discrete_input('wakerotation', val=True,                        desc='include effect of wake rotation (i.e., tangential induction factor is nonzero)')
#         self.add_discrete_input('usecd',     val=True,                           desc='use drag coefficient in computing induction factors')

#         # outputs
#         self.add_output('V',        val=np.zeros(n_pc), units='m/s',  desc='wind vector')
#         self.add_output('Omega',    val=np.zeros(n_pc), units='rpm',  desc='rotor rotational speed')
#         self.add_output('pitch',    val=np.zeros(n_pc), units='deg',  desc='rotor pitch schedule')
#         self.add_output('P',        val=np.zeros(n_pc), units='W',    desc='rotor electrical power')
#         self.add_output('T',        val=np.zeros(n_pc), units='N',    desc='rotor aerodynamic thrust')
#         self.add_output('Q',        val=np.zeros(n_pc), units='N*m',  desc='rotor aerodynamic torque')
#         self.add_output('M',        val=np.zeros(n_pc), units='N*m',  desc='blade root moment')
#         self.add_output('Cp',       val=np.zeros(n_pc),               desc='rotor electrical power coefficient')

#         self.add_output('V_spline', val=np.zeros(n_pc_spline), units='m/s',  desc='wind vector')
#         self.add_output('P_spline', val=np.zeros(n_pc_spline), units='W',    desc='rotor electrical power')
        
#         self.add_output('rated_V',     val=0.0, units='m/s', desc='rated wind speed')
#         self.add_output('rated_Omega', val=0.0, units='rpm', desc='rotor rotation speed at rated')
#         self.add_output('rated_pitch', val=0.0, units='deg', desc='pitch setting at rated')
#         self.add_output('rated_T',     val=0.0, units='N', desc='rotor aerodynamic thrust at rated')
#         self.add_output('rated_Q',     val=0.0, units='N*m', desc='rotor aerodynamic torque at rated')

#         self.naero                      = naero
#         self.n_pc                       = n_pc
#         self.n_pc_spline                = n_pc_spline
#         self.lock_pitchII               = False
#         self.regulation_reg_II5         = regulation_reg_II5
#         self.regulation_reg_III         = regulation_reg_III
        
#     def compute(self, inputs, outputs):
                
#         self.ccblade = CCBlade(inputs['r'], inputs['chord'], inputs['theta'], inputs['airfoils'], inputs['Rhub'], inputs['Rtip'], inputs['B'], inputs['rho'], inputs['mu'], inputs['precone'], inputs['tilt'], inputs['yaw'], inputs['shearExp'], inputs['hubHt'], inputs['nSector'])        
        
#         Uhub    = np.linspace(inputs['control_Vin'],inputs['control_Vout'], self.n_pc)
        
#         P_aero   = np.zeros_like(Uhub)
#         Cp_aero  = np.zeros_like(Uhub)
#         P       = np.zeros_like(Uhub)
#         Cp      = np.zeros_like(Uhub)
#         T       = np.zeros_like(Uhub)
#         Q       = np.zeros_like(Uhub)
#         M       = np.zeros_like(Uhub)
#         Omega   = np.zeros_like(Uhub)
#         pitch   = np.zeros_like(Uhub) + inputs['control_pitch']
        
#         # Region II
#         for i in range(len(Uhub)):
#             Omega[i] = Uhub[i] * inputs['control_tsr'] / inputs['Rtip']
        
#         P_aero, T, Q, M, Cp_aero, _, _, _ = self.ccblade.evaluate(Uhub, Omega * 30. / np.pi, pitch, coefficients=True)
#         P, eff  = CSMDrivetrain(P_aero, inputs['control_ratedPower'], inputs['drivetrainType'], inputs['drivetrainEff'])
#         Cp      = Cp_aero*eff

        
#         for i in range(len(Uhub)):
#             if P  [i] > inputs['control_ratedPower']:
#                 regionIIhalf = False
#                 break
#             if Omega[i] * inputs['Rtip'] > inputs['control_maxTS']:
#                 regionIIhalf = True
#                 break

        
#         def maxPregionIIhalf(pitch, Uhub, Omega):
#             Uhub_i  = Uhub
#             Omega_i = Omega
#             pitch   = pitch
                        
#             P, _, _, _ = self.ccblade.evaluate([Uhub_i], [Omega_i * 30. / np.pi], [pitch], coefficients=False)
#             return -P
        
#         options             = {}
#         if regionIIhalf == True:
#             for i in range(len(Uhub)):
#                 if Omega[i] * inputs['Rtip'] > inputs['control_maxTS']:
                    
#                     Omega[i] = inputs['control_maxTS'] / inputs['Rtip']
#                     pitch0 = pitch[i-1]
                    
#                     options['disp']     = False
#                     bnds = [pitch0 - 10., pitch0 + 10.]
#                     pitch_regionIIhalf = minimize_scalar(lambda x: maxPregionIIhalf(x, Uhub[i], Omega[i]), bounds=bnds, method='bounded', options=options)['x']
#                     pitch[i] = pitch_regionIIhalf
                    
                    
#                     P_aero[i], T[i], Q[i], M[i], Cp_aero[i], _, _, _ = self.ccblade.evaluate([Uhub[i]], [Omega[i] * 30. / np.pi], [pitch[i]], coefficients=True)
#                     P, eff  = CSMDrivetrain(P_aero, inputs['control_ratedPower'], inputs['drivetrainType'], inputs['drivetrainEff'])
#                     Cp      = Cp_aero*eff

#                     if P  [i] > inputs['control_ratedPower']:
#                         break

        
#         def constantPregionIII(pitch, Uhub, Omega, targetP, init_pitch):
#             Uhub_i  = Uhub
#             Omega_i = Omega
#             pitch   = pitch
                        
#             P_aero, _, _, _ = self.ccblade.evaluate([Uhub_i], [Omega_i * 30. / np.pi], [pitch], coefficients=False)
#             P, eff          = CSMDrivetrain(P_aero, inputs['control_ratedPower'], inputs['drivetrainType'], inputs['drivetrainEff'])
            
#             return abs(P - targetP)
            
#         # Region III       
#         U_rated   = Uhub[i]
#         for j in range(i,len(Uhub)):
#             Omega[j]  = Omega[i]
#             if self.regulation_reg_III == True:
#                 pitch0          = pitch[j-1]
#                 bnds            = [pitch0, pitch0 + 10.]
                
#                 pitch_regionIII = minimize_scalar(lambda x: constantPregionIII(x, Uhub[j], Omega[j], inputs['control_ratedPower'], pitch0), bounds=bnds, method='bounded', options=options)['x']
                
#                 pitch[j]        = pitch_regionIII
#                 P_aero[j], T[j], Q[j], M[j], Cp_aero[j], _, _, _ = self.ccblade.evaluate([Uhub[j]], [Omega[j] * 30. / np.pi], [pitch[j]], coefficients=True)
#                 P, eff          = CSMDrivetrain(P_aero[j], inputs['control_ratedPower'], inputs['drivetrainType'], inputs['drivetrainEff'])
#                 Cp              = Cp_aero*eff
                
#                 if abs(P[j] - inputs['control_ratedPower']) > 1e+4:
#                     print('The pitch in region III is not being determined correctly at wind speed ' + str(Uhub[j]) + ' m/s')
#                     P  [j]      = inputs['control_ratedPower']
#                     T[j]        = T[j-1]
#                     Q[j]        = P  [j] / Omega[j]
#                     M[j]        = M[j-1]
#                     pitch[j]    = pitch[j-1]
#                     Cp  [j]     = P  [j] / (0.5 * inputs['rho'] * np.pi * inputs['Rtip']**2 * Uhub[i]**3)
#                     P, eff      = CSMDrivetrain(P_aero, inputs['control_ratedPower'], inputs['drivetrainType'], inputs['drivetrainEff'])
#                     Cp          = Cp_aero*eff
                
#             else:
#                 P[j]        = inputs['control_ratedPower']
#                 T[j]        = 0
#                 Q[j]        = P  [j] / Omega[j]
#                 M[j]        = 0
#                 pitch[j]    = 0
#                 Cp  [j]     = P[j] / (0.5 * inputs['rho'] * np.pi * inputs['Rtip']**2 * Uhub[i]**3)

        
#         outputs['T']       = T
#         outputs['Q']       = Q
#         outputs['Omega']   = Omega * 30 / np.pi
        
#         outputs['P']       = P  
#         outputs['Cp']      = Cp  
#         outputs['V']       = Uhub
#         outputs['M']       = M
#         outputs['pitch']   = pitch
        
        
#         # Fit spline to powercurve for higher grid density, make sure using unique values first
#         Uniq, iniq = np.unique(Uhub, return_index=True)
#         spline   = PchipInterpolator(Uniq, P[iniq])
#         V_spline = np.linspace(inputs['control_Vin'],inputs['control_Vout'], num=self.n_pc_spline)
#         P_spline = spline(V_spline)
        
        
#         # outputs
#         idx_rated = list(Uhub).index(U_rated)
#         outputs['rated_V']     = U_rated
#         outputs['rated_Omega'] = Omega[idx_rated]
#         outputs['rated_pitch'] = pitch[idx_rated]
#         outputs['rated_T'   ]  = T[idx_rated]
#         outputs['rated_Q']     = Q[idx_rated]
        
#         outputs['V_spline']    = V_spline
#         outputs['P_spline']    = P_spline
        
        
class RegulatedPowerCurve(ExplicitComponent): # Implicit COMPONENT

    def initialize(self):
        self.options.declare('naero')
        self.options.declare('n_pc')
        self.options.declare('n_pc_spline')
        self.options.declare('regulation_reg_II5',default=True)
        self.options.declare('regulation_reg_III',default=False)
    
    def setup(self):
        naero = self.options['naero']
        n_pc = self.options['n_pc']
        n_pc_spline = self.options['n_pc_spline']
        self.lock_pitchII       = False

        # parameters
        self.add_input('control_Vin',        val=0.0, units='m/s',  desc='cut-in wind speed')
        self.add_input('control_Vout',       val=0.0, units='m/s',  desc='cut-out wind speed')
        self.add_input('control_ratedPower', val=0.0, units='W',    desc='electrical rated power')
        self.add_input('control_minOmega',   val=0.0, units='rpm',  desc='minimum allowed rotor rotation speed')
        self.add_input('control_maxOmega',   val=0.0, units='rpm',  desc='maximum allowed rotor rotation speed')
        self.add_input('control_maxTS',      val=0.0, units='m/s',  desc='maximum allowed blade tip speed')
        self.add_input('control_tsr',        val=0.0,               desc='tip-speed ratio in Region 2 (should be optimized externally)')
        self.add_input('control_pitch',      val=0.0, units='deg',  desc='pitch angle in region 2 (and region 3 for fixed pitch machines)')
        self.add_discrete_input('drivetrainType',     val='GEARED')
        self.add_input('drivetrainEff',     val=0.0,               desc='overwrite drivetrain model with a given efficiency, used for FAST analysis')
        
        self.add_input('r',         val=np.zeros(naero), units='m',   desc='radial locations where blade is defined (should be increasing and not go all the way to hub or tip)')
        self.add_input('chord',     val=np.zeros(naero), units='m',   desc='chord length at each section')
        self.add_input('theta',     val=np.zeros(naero), units='deg', desc='twist angle at each section (positive decreases angle of attack)')
        self.add_input('Rhub',      val=0.0,             units='m',   desc='hub radius')
        self.add_input('Rtip',      val=0.0,             units='m',   desc='tip radius')
        self.add_input('hubHt',     val=0.0,             units='m',   desc='hub height')
        self.add_input('precone',   val=0.0,             units='deg', desc='precone angle', )
        self.add_input('tilt',      val=0.0,             units='deg', desc='shaft tilt', )
        self.add_input('yaw',       val=0.0,             units='deg', desc='yaw error', )
        self.add_input('precurve',      val=np.zeros(naero),    units='m', desc='precurve at each section')
        self.add_input('precurveTip',   val=0.0,                units='m', desc='precurve at tip')

        self.add_discrete_input('airfoils',  val=[0]*naero,                      desc='CCAirfoil instances')
        self.add_discrete_input('nBlades',         val=0,                              desc='number of blades')
        self.add_input('rho',       val=0.0,        units='kg/m**3',    desc='density of air')
        self.add_input('mu',        val=0.0,        units='kg/(m*s)',   desc='dynamic viscosity of air')
        self.add_input('shearExp',  val=0.0,                            desc='shear exponent')
        self.add_discrete_input('nSector',   val=4,                              desc='number of sectors to divide rotor face into in computing thrust and power')
        self.add_discrete_input('tiploss',   val=True,                           desc='include Prandtl tip loss model')
        self.add_discrete_input('hubloss',   val=True,                           desc='include Prandtl hub loss model')
        self.add_discrete_input('wakerotation', val=True,                        desc='include effect of wake rotation (i.e., tangential induction factor is nonzero)')
        self.add_discrete_input('usecd',     val=True,                           desc='use drag coefficient in computing induction factors')

        # outputs
        self.add_output('V',        val=np.zeros(n_pc), units='m/s',    desc='wind vector')
        self.add_output('Omega',    val=np.zeros(n_pc), units='rpm',    desc='rotor rotational speed')
        self.add_output('pitch',    val=np.zeros(n_pc), units='deg',    desc='rotor pitch schedule')
        self.add_output('P',        val=np.zeros(n_pc), units='W',      desc='rotor electrical power')
        self.add_output('T',        val=np.zeros(n_pc), units='N',      desc='rotor aerodynamic thrust')
        self.add_output('Q',        val=np.zeros(n_pc), units='N*m',    desc='rotor aerodynamic torque')
        self.add_output('M',        val=np.zeros(n_pc), units='N*m',    desc='blade root moment')
        self.add_output('Cp',       val=np.zeros(n_pc),                 desc='rotor electrical power coefficient')
        self.add_output('V_spline', val=np.zeros(n_pc_spline), units='m/s',  desc='wind vector')
        self.add_output('P_spline', val=np.zeros(n_pc_spline), units='W',    desc='rotor electrical power')
        self.add_output('V_R25',       val=0.0, units='m/s', desc='region 2.5 transition wind speed')
        self.add_output('rated_V',     val=0.0, units='m/s', desc='rated wind speed')
        self.add_output('rated_Omega', val=0.0, units='rpm', desc='rotor rotation speed at rated')
        self.add_output('rated_pitch', val=0.0, units='deg', desc='pitch setting at rated')
        self.add_output('rated_T',     val=0.0, units='N',   desc='rotor aerodynamic thrust at rated')
        self.add_output('rated_Q',     val=0.0, units='N*m', desc='rotor aerodynamic torque at rated')
        self.add_output('ax_induct_cutin',   val=np.zeros(naero), desc='rotor axial induction at cut-in wind speed along blade span')
        self.add_output('tang_induct_cutin', val=np.zeros(naero), desc='rotor tangential induction at cut-in wind speed along blade span')
        self.add_output('aoa_cutin',         val=np.zeros(naero), desc='angle of attack distribution along blade span at cut-in wind speed')

        self.declare_partials('*', '*', method='fd', form='central', step=1e-6)
        
    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
                
        self.ccblade = CCBlade(inputs['r'], inputs['chord'], inputs['theta'], discrete_inputs['airfoils'], inputs['Rhub'], inputs['Rtip'], discrete_inputs['nBlades'], inputs['rho'], inputs['mu'], inputs['precone'], inputs['tilt'], inputs['yaw'], inputs['shearExp'], inputs['hubHt'], discrete_inputs['nSector'])
        
        Uhub    = np.linspace(inputs['control_Vin'],inputs['control_Vout'], self.options['n_pc']).flatten()
        P_aero   = np.zeros_like(Uhub)
        Cp_aero  = np.zeros_like(Uhub)
        P       = np.zeros_like(Uhub)
        Cp      = np.zeros_like(Uhub)
        T       = np.zeros_like(Uhub)
        Q       = np.zeros_like(Uhub)
        M       = np.zeros_like(Uhub)
        Omega   = np.zeros_like(Uhub)
        pitch   = np.zeros_like(Uhub) + inputs['control_pitch']

        Omega_max = min([inputs['control_maxTS'] / inputs['Rtip'], inputs['control_maxOmega']*np.pi/30.])
        
        # Region II
        for i in range(len(Uhub)):
            Omega[i] = Uhub[i] * inputs['control_tsr'] / inputs['Rtip']
        
        P_aero, T, Q, M, Cp_aero, _, _, _ = self.ccblade.evaluate(Uhub, Omega * 30. / np.pi, pitch, coefficients=True)
        P, eff  = CSMDrivetrain(P_aero, inputs['control_ratedPower'], discrete_inputs['drivetrainType'], inputs['drivetrainEff'])
        Cp      = Cp_aero*eff
        
        # search for Region 2.5 bounds
        for i in range(len(Uhub)):
        
            if Omega[i] > Omega_max and P[i] < inputs['control_ratedPower']:
                Omega[i]        = Omega_max
                Uhub[i]         = Omega[i] * inputs['Rtip'] / inputs['control_tsr']
                P_aero[i], T[i], Q[i], M[i], Cp_aero[i], _, _, _ = self.ccblade.evaluate([Uhub[i]], [Omega[i] * 30. / np.pi], [pitch[i]], coefficients=True)
                P[i], eff       = CSMDrivetrain(P_aero[i], inputs['control_ratedPower'], discrete_inputs['drivetrainType'], inputs['drivetrainEff'])
                Cp[i]           = Cp_aero[i]*eff
                regionIIhalf    = True
                i_IIhalf_start  = i

                outputs['V_R25'] = Uhub[i]
                break

            if P[i] > inputs['control_ratedPower']:
                regionIIhalf = False
                break

        
        def maxPregionIIhalf(pitch, Uhub, Omega):
            Uhub_i  = Uhub
            Omega_i = Omega
            pitch   = pitch
                        
            P, _, _, _ = self.ccblade.evaluate([Uhub_i], [Omega_i * 30. / np.pi], [pitch], coefficients=False)
            return -P
        
        # Solve for regoin 2.5 pitch
        options             = {}
        options['disp']     = False
        options['xatol']    = 1.e-2
        if regionIIhalf == True:
            for i in range(i_IIhalf_start + 1, len(Uhub)):   
                Omega[i]    = Omega_max
                pitch0      = pitch[i-1]
                
                bnds        = [pitch0 - 10., pitch0 + 10.]
                pitch_regionIIhalf = minimize_scalar(lambda x: maxPregionIIhalf(x, Uhub[i], Omega[i]), bounds=bnds, method='bounded', options=options)['x']
                pitch[i]    = pitch_regionIIhalf
                
                P_aero[i], T[i], Q[i], M[i], Cp_aero[i], _, _, _ = self.ccblade.evaluate([Uhub[i]], [Omega[i] * 30. / np.pi], [pitch[i]], coefficients=True)
                
                P[i], eff  = CSMDrivetrain(P_aero[i], inputs['control_ratedPower'], discrete_inputs['drivetrainType'], inputs['drivetrainEff'])
                Cp[i]      = Cp_aero[i]*eff

                if P[i] > inputs['control_ratedPower']:    
                    break    

        def constantPregionIII(pitch, Uhub, Omega):
            Uhub_i  = Uhub
            Omega_i = Omega
            pitch   = pitch           
            P_aero, _, _, _ = self.ccblade.evaluate([Uhub_i], [Omega_i * 30. / np.pi], [pitch], coefficients=False)
            P, eff          = CSMDrivetrain(P_aero, inputs['control_ratedPower'], discrete_inputs['drivetrainType'], inputs['drivetrainEff'])
            return abs(P - inputs['control_ratedPower'])
            

        
        if regionIIhalf == True:
            # Rated conditions
            
            def min_Uhub_rated_II12(min_inputs):
                return min_inputs[1]
                
            def get_Uhub_rated_II12(min_inputs):

                Uhub_i  = min_inputs[1]
                Omega_i = Omega_max
                pitch   = min_inputs[0]           
                P_aero_i, _, _, _ = self.ccblade.evaluate([Uhub_i], [Omega_i * 30. / np.pi], [pitch], coefficients=False)
                P_i,eff          = CSMDrivetrain(P_aero_i.flatten(), inputs['control_ratedPower'], discrete_inputs['drivetrainType'], inputs['drivetrainEff'])
                return abs(P_i - inputs['control_ratedPower'])

            x0              = [pitch[i] + 2. , Uhub[i]]
            bnds            = [(pitch0, pitch0 + 10.),(Uhub[i-1],Uhub[i+1])]
            const           = {}
            const['type']   = 'eq'
            const['fun']    = get_Uhub_rated_II12
            inputs_rated    = minimize(min_Uhub_rated_II12, x0, method='SLSQP', tol = 1.e-2, bounds=bnds, constraints=const)
            U_rated         = inputs_rated.x[1]
            
            if not np.isnan(U_rated):
                Uhub[i]         = U_rated
                pitch[i]        = inputs_rated.x[0]
            else:
                print('Regulation trajectory is struggling to find a solution for rated wind speed. Check rotor_aeropower.py')
            
            Omega[i]        = Omega_max
            P_aero[i], T[i], Q[i], M[i], Cp_aero[i], _, _, _ = self.ccblade.evaluate([Uhub[i]], [Omega[i] * 30. / np.pi], [pitch0], coefficients=True)
            P_i, eff        = CSMDrivetrain(P_aero[i], inputs['control_ratedPower'], discrete_inputs['drivetrainType'], inputs['drivetrainEff'])
            Cp[i]           = Cp_aero[i]*eff
            P[i]            = inputs['control_ratedPower']
            
            
        else:
            # Rated conditions
            def get_Uhub_rated_noII12(pitch, Uhub):
                Uhub_i  = Uhub
                Omega_i = min([Uhub_i * inputs['control_tsr'] / inputs['Rtip'], Omega_max])
                pitch_i = pitch           
                P_aero_i, _, _, _ = self.ccblade.evaluate([Uhub_i], [Omega_i * 30. / np.pi], [pitch_i], coefficients=False)
                P_i, eff          = CSMDrivetrain(P_aero_i, inputs['control_ratedPower'], discrete_inputs['drivetrainType'], inputs['drivetrainEff'])
                return abs(P_i - inputs['control_ratedPower'])
            
            bnds     = [Uhub[i-1], Uhub[i+1]]
            U_rated  = minimize_scalar(lambda x: get_Uhub_rated_noII12(pitch[i], x), bounds=bnds, method='bounded', options=options)['x']
            
            if not np.isnan(U_rated):
                Uhub[i]         = U_rated
            else:
                print('Regulation trajectory is struggling to find a solution for rated wind speed. Check rotor_aeropower.py')
            
            
            
            
            
            Omega[i] = min([Uhub[i] * inputs['control_tsr'] / inputs['Rtip'], Omega_max])
            pitch0   = pitch[i]
            
            P_aero[i], T[i], Q[i], M[i], Cp_aero[i], _, _, _ = self.ccblade.evaluate([Uhub[i]], [Omega[i] * 30. / np.pi], [pitch0], coefficients=True)
            P[i], eff    = CSMDrivetrain(P_aero[i], inputs['control_ratedPower'], discrete_inputs['drivetrainType'], inputs['drivetrainEff'])
            Cp[i]        = Cp_aero[i]*eff
        
        
        for j in range(i + 1,len(Uhub)):
            Omega[j] = Omega[i]
            if self.options['regulation_reg_III']:
                
                pitch0   = pitch[j-1]
                bnds     = [pitch0, pitch0 + 15.]
                pitch_regionIII = minimize_scalar(lambda x: constantPregionIII(x, Uhub[j], Omega[j]), bounds=bnds, method='bounded', options=options)['x']
                pitch[j]        = pitch_regionIII
                
                P_aero[j], T[j], Q[j], M[j], Cp_aero[j], _, _, _ = self.ccblade.evaluate([Uhub[j]], [Omega[j] * 30. / np.pi], [pitch[j]], coefficients=True)
                P[j], eff       = CSMDrivetrain(P_aero[j], inputs['control_ratedPower'], discrete_inputs['drivetrainType'], inputs['drivetrainEff'])
                Cp[j]           = Cp_aero[j]*eff


                if abs(P[j] - inputs['control_ratedPower']) > 1e+4:
                    print('The pitch in region III is not being determined correctly at wind speed ' + str(Uhub[j]) + ' m/s')
                    P[j]        = inputs['control_ratedPower']
                    T[j]        = T[j-1]
                    Q[j]        = P[j] / Omega[j]
                    M[j]        = M[j-1]
                    pitch[j]    = pitch[j-1]
                    Cp[j]       = P[j] / (0.5 * inputs['rho'] * np.pi * inputs['Rtip']**2 * Uhub[i]**3)

                P[j] = inputs['control_ratedPower']
                
            else:
                P[j]        = inputs['control_ratedPower']
                T[j]        = 0
                Q[j]        = Q[i]
                M[j]        = 0
                pitch[j]    = 0
                Cp[j]       = P[j] / (0.5 * inputs['rho'] * np.pi * inputs['Rtip']**2 * Uhub[i]**3)

        
        outputs['T']       = T
        outputs['Q']       = Q
        outputs['Omega']   = Omega * 30. / np.pi


        outputs['P']       = P  
        outputs['Cp']      = Cp  
        outputs['V']       = Uhub
        outputs['M']       = M
        outputs['pitch']   = pitch
        
        
        self.ccblade.induction_inflow = True
        a_regII, ap_regII, alpha_regII, _, _ = self.ccblade.distributedAeroLoads(Uhub[0], Omega[0] * 30. / np.pi, pitch[0], 0.0)
        
        # Fit spline to powercurve for higher grid density
        spline   = PchipInterpolator(Uhub, P)
        V_spline = np.linspace(inputs['control_Vin'],inputs['control_Vout'], num=self.options['n_pc_spline'])
        P_spline = spline(V_spline)
        
        # outputs
        idx_rated = list(Uhub).index(U_rated)
        outputs['rated_V']     = U_rated.flatten()
        outputs['rated_Omega'] = Omega[idx_rated] * 30. / np.pi
        outputs['rated_pitch'] = pitch[idx_rated]
        outputs['rated_T']     = T[idx_rated]
        outputs['rated_Q']     = Q[idx_rated]
        outputs['V_spline']    = V_spline.flatten()
        outputs['P_spline']    = P_spline.flatten()
        outputs['ax_induct_cutin']   = a_regII
        outputs['tang_induct_cutin'] = ap_regII
        outputs['aoa_cutin']         = alpha_regII
        

class AEP(ExplicitComponent):
    def initialize(self):
        self.options.declare('n_pc_spline')
    
    def setup(self):
        n_pc_spline = self.options['n_pc_spline']
        """integrate to find annual energy production"""

        # inputs
        self.add_input('CDF_V', val=np.zeros(n_pc_spline), units='m/s', desc='cumulative distribution function evaluated at each wind speed')
        self.add_input('P', val=np.zeros(n_pc_spline), units='W', desc='power curve (power)')
        self.add_input('lossFactor', val=0.0, desc='multiplicative factor for availability and other losses (soiling, array, etc.)')

        # outputs
        self.add_output('AEP', val=0.0, units='kW*h', desc='annual energy production')

        self.declare_partials('*', '*', method='fd', form='central', step=1e-6)

    def compute(self, inputs, outputs):

        outputs['AEP'] = inputs['lossFactor']*np.trapz(inputs['P'], inputs['CDF_V'])/1e3*365.0*24.0  # in kWh

    def list_deriv_vars(self):

        inputs = ('CDF_V', 'P', 'lossFactor')
        outputs = ('AEP',)

        return inputs, outputs


    def compute_partials(self, inputs, J):

        lossFactor = inputs['lossFactor']
        P = inputs['P']
        factor = lossFactor/1e3*365.0*24.0

        dAEP_dP, dAEP_dCDF = trapz_deriv(P, inputs['CDF_V'])
        dAEP_dP *= factor
        dAEP_dCDF *= factor

        dAEP_dlossFactor = np.array([outputs['AEP']/lossFactor])

        J = {}
        J['AEP', 'CDF_V'] = np.reshape(dAEP_dCDF, (1, len(dAEP_dCDF)))
        J['AEP', 'P'] = np.reshape(dAEP_dP, (1, len(dAEP_dP)))
        J['AEP', 'lossFactor'] = dAEP_dlossFactor

        return J


def CSMDrivetrain(aeroPower, ratedPower, drivetrainType, drivetrainEff):

    if drivetrainEff == 0.0:
        drivetrainType = drivetrainType.upper()
        if drivetrainType == 'GEARED':
            constant = 0.01289
            linear = 0.08510
            quadratic = 0.0

        elif drivetrainType == 'SINGLE_STAGE':
            constant = 0.01331
            linear = 0.03655
            quadratic = 0.06107

        elif drivetrainType == 'MULTI_DRIVE':
            constant = 0.01547
            linear = 0.04463
            quadratic = 0.05790

        elif drivetrainType == 'PM_DIRECT_DRIVE':
            constant = 0.01007
            linear = 0.02000
            quadratic = 0.06899

        Pbar0 = aeroPower / ratedPower

        # handle negative power case (with absolute value)
        Pbar1, dPbar1_dPbar0 = smooth_abs(Pbar0, dx=0.01)

        # truncate idealized power curve for purposes of efficiency calculation
        Pbar, dPbar_dPbar1, _ = smooth_min(Pbar1, 1.0, pct_offset=0.01)

        # compute efficiency
        eff = 1.0 - (constant/Pbar + linear + quadratic*Pbar)
    else:
        eff = drivetrainEff
        
    return aeroPower * eff, eff


class OutputsAero(ExplicitComponent):
    def initialize(self):
        self.options.declare('npts_coarse_power_curve')
    
    def setup(self):
        npts_coarse_power_curve = self.options['npts_coarse_power_curve']

        # --- outputs ---
        self.add_input('AEP_in', val=0.0, units='kW*h', desc='annual energy production')
        self.add_input('V_in', val=np.zeros(npts_coarse_power_curve), units='m/s', desc='wind speeds (power curve)')
        self.add_input('P_in', val=np.zeros(npts_coarse_power_curve), units='W', desc='power (power curve)')

        self.add_input('rated_V_in', val=0.0, units='m/s', desc='rated wind speed')
        self.add_input('rated_Omega_in', val=0.0, units='rpm', desc='rotor rotation speed at rated')
        self.add_input('rated_pitch_in', val=0.0, units='deg', desc='pitch setting at rated')
        self.add_input('rated_T_in', val=0.0, units='N', desc='rotor aerodynamic thrust at rated')
        self.add_input('rated_Q_in', val=0.0, units='N*m', desc='rotor aerodynamic torque at rated')

        self.add_input('diameter_in', val=0.0, units='m', desc='rotor diameter')
        self.add_input('V_extreme_in', val=0.0, units='m/s', desc='survival wind speed')
        self.add_input('T_extreme_in', val=0.0, units='N', desc='thrust at survival wind condition')
        self.add_input('Q_extreme_in', val=0.0, units='N*m', desc='thrust at survival wind condition')

        # --- outputs ---
        self.add_output('AEP', val=0.0, units='kW*h', desc='annual energy production')
        self.add_output('V', val=np.zeros(npts_coarse_power_curve), units='m/s', desc='wind speeds (power curve)')
        self.add_output('P', val=np.zeros(npts_coarse_power_curve), units='W', desc='power (power curve)')

        self.add_output('rated_V', val=0.0, units='m/s', desc='rated wind speed')
        self.add_output('rated_Omega', val=0.0, units='rpm', desc='rotor rotation speed at rated')
        self.add_output('rated_pitch', val=0.0, units='deg', desc='pitch setting at rated')
        self.add_output('rated_T', val=0.0, units='N', desc='rotor aerodynamic thrust at rated')
        self.add_output('rated_Q', val=0.0, units='N*m', desc='rotor aerodynamic torque at rated')

        self.add_output('diameter', val=0.0, units='m', desc='rotor diameter')
        self.add_output('V_extreme', val=0.0, units='m/s', desc='survival wind speed')
        self.add_output('T_extreme', val=0.0, units='N', desc='thrust at survival wind condition')
        self.add_output('Q_extreme', val=0.0, units='N*m', desc='thrust at survival wind condition')

        self.declare_partials('AEP', 'AEP_in')
        self.declare_partials('V', 'V_in')
        self.declare_partials('P', 'P_in')
        self.declare_partials('rated_V', 'rated_V_in')
        self.declare_partials('rated_Omega', 'rated_Omega_in')
        self.declare_partials('rated_pitch', 'rated_pitch_in')
        self.declare_partials('rated_T', 'rated_T_in')
        self.declare_partials('rated_Q', 'rated_Q_in')
        self.declare_partials('diameter', 'diameter_in')
        self.declare_partials('V_extreme', 'V_extreme_in')
        self.declare_partials('T_extreme', 'T_extreme_in')
        self.declare_partials('Q_extreme', 'Q_extreme_in')
        
    def compute(self, inputs, outputs):
        outputs['AEP'] = inputs['AEP_in']
        outputs['V'] = inputs['V_in']
        outputs['P'] = inputs['P_in']
        outputs['rated_V'] = inputs['rated_V_in']
        outputs['rated_Omega'] = inputs['rated_Omega_in']
        outputs['rated_pitch'] = inputs['rated_pitch_in']
        outputs['rated_T'] = inputs['rated_T_in']
        outputs['rated_Q'] = inputs['rated_Q_in']
        outputs['diameter'] = inputs['diameter_in']
        outputs['V_extreme'] = inputs['V_extreme_in']
        outputs['T_extreme'] = inputs['T_extreme_in']
        outputs['Q_extreme'] = inputs['Q_extreme_in']

    def compute_partials(self, inputs, J):
        J['AEP', 'AEP_in'] = 1
        J['V', 'V_in'] = np.diag(np.ones(len(inputs['V_in'])))
        J['P', 'P_in'] = np.diag(np.ones(len(inputs['P_in'])))
        J['rated_V', 'rated_V_in'] = 1
        J['rated_Omega', 'rated_Omega_in'] = 1
        J['rated_pitch', 'rated_pitch_in'] = 1
        J['rated_T', 'rated_T_in'] = 1
        J['rated_Q', 'rated_Q_in'] = 1
        J['diameter', 'diameter_in'] = 1
        J['V_extreme', 'V_extreme_in'] = 1
        J['T_extreme', 'T_extreme_in'] = 1
        J['Q_extreme', 'Q_extreme_in'] = 1

        

class RotorAeroPower(Group):
    def initialize(self):
        self.options.declare('RefBlade')
        self.options.declare('npts_coarse_power_curve', default=20)
        self.options.declare('npts_spline_power_curve', default=200)
        self.options.declare('regulation_reg_II5',default=True)
        self.options.declare('regulation_reg_III',default=True)
        self.options.declare('topLevelFlag',default=False)
    
    def setup(self):
        RefBlade = self.options['RefBlade']
        npts_coarse_power_curve  = self.options['npts_coarse_power_curve']
        npts_spline_power_curve  = self.options['npts_spline_power_curve']
        regulation_reg_II5 = self.options['regulation_reg_II5']
        regulation_reg_III = self.options['regulation_reg_III']
        topLevelFlag = self.options['topLevelFlag']

        aeroIndeps = IndepVarComp()
        aeroIndeps.add_output('wind_reference_height', val=0.0, units='m', desc='reference hub height for IEC wind speed (used in CDF calculation)')
        aeroIndeps.add_output('control_Vin', val=0.0, units='m/s', desc='cut-in wind speed')
        aeroIndeps.add_output('control_Vout', val=0.0, units='m/s', desc='cut-out wind speed')
        aeroIndeps.add_output('machine_rating', val=0.0,  units='W', desc='rated power')
        aeroIndeps.add_output('control_minOmega', val=0.0, units='rpm', desc='minimum allowed rotor rotation speed')
        aeroIndeps.add_output('control_maxOmega', val=0.0, units='rpm', desc='maximum allowed rotor rotation speed')
        aeroIndeps.add_output('control_maxTS', val=0.0, units='m/s', desc='maximum allowed blade tip speed')
        aeroIndeps.add_output('control_tsr', val=0.0, desc='tip-speed ratio in Region 2 (should be optimized externally)')
        aeroIndeps.add_output('control_pitch', val=0.0, units='deg', desc='pitch angle in region 2 (and region 3 for fixed pitch machines)')
        aeroIndeps.add_discrete_output('drivetrainType', val='GEARED')
        aeroIndeps.add_output('AEP_loss_factor', val=1.0, desc='availability and other losses (soiling, array, etc.)')
        aeroIndeps.add_output('shape_parameter', val=0.0)
        aeroIndeps.add_output('drivetrainEff', val=0.0, desc='overwrite drivetrain model with a given efficiency, used for FAST analysis')
        self.add_subsystem('aeroIndeps', aeroIndeps, promotes=['*'])
        
        # --- Rotor Aero & Power ---
        if topLevelFlag:
            sharedIndeps = IndepVarComp()
            sharedIndeps.add_output('hubHt', val=0.0, units='m')
            sharedIndeps.add_output('rho', val=1.225, units='kg/m**3')
            sharedIndeps.add_output('mu', val=1.81e-5, units='kg/(m*s)')
            sharedIndeps.add_output('shearExp', val=0.2)
            sharedIndeps.add_discrete_output('tiploss', True)
            sharedIndeps.add_discrete_output('hubloss', True)
            sharedIndeps.add_discrete_output('wakerotation', True)
            sharedIndeps.add_discrete_output('usecd', True)
            sharedIndeps.add_discrete_output('nSector', val=4, desc='number of sectors to divide rotor face into in computing thrust and power')
            self.add_subsystem('sharedIndeps', sharedIndeps, promotes=['*'])
            
        self.add_subsystem('rotorGeom', RotorGeometry(RefBlade=RefBlade, topLevelFlag=True), promotes=['*'])

        # self.add_subsystem('tipspeed', MaxTipSpeed())
        self.add_subsystem('powercurve', RegulatedPowerCurve(naero=RefBlade.npts,
                                                             n_pc=npts_coarse_power_curve,
                                                             n_pc_spline=npts_spline_power_curve,
                                                             regulation_reg_II5=regulation_reg_II5,
                                                             regulation_reg_III=regulation_reg_III),
                           promotes=['hubHt','precurveTip','precone','tilt','yaw','nBlades','rho','mu',
                                     'shearExp','nSector','tiploss','hubloss','wakerotation','usecd'])
        self.add_subsystem('wind', PowerWind(nPoints=1), promotes=['shearExp'])
        # self.add_subsystem('cdf', WeibullWithMeanCDF(nspline=npts_coarse_power_curve))
        self.add_subsystem('cdf', RayleighCDF(nspline=npts_spline_power_curve))
        self.add_subsystem('aep', AEP(n_pc_spline=npts_spline_power_curve))

        self.add_subsystem('outputs_aero', OutputsAero(npts_coarse_power_curve=npts_coarse_power_curve), promotes=['*'])

        # connections to analysis
        self.connect('r_pts', 'powercurve.r')
        self.connect('chord', 'powercurve.chord')
        self.connect('theta', 'powercurve.theta')
        self.connect('precurve', 'powercurve.precurve')
        #self.connect('precurveTip', 'powercurve.precurveTip')
        self.connect('Rhub', 'powercurve.Rhub')
        self.connect('Rtip', 'powercurve.Rtip')
        #self.connect('hub_height', 'powercurve.hubHt')
        #self.connect('precone', 'powercurve.precone')
        #self.connect('tilt', 'powercurve.tilt')
        #self.connect('yaw', 'powercurve.yaw')
        self.connect('airfoils', 'powercurve.airfoils')
        #self.connect('nBlades', 'powercurve.nBlades')
        #self.connect('rho', 'powercurve.rho')
        #self.connect('mu', 'powercurve.mu')
        #self.connect('shearExp', 'powercurve.shearExp')
        #self.connect('nSector', 'powercurve.nSector')
        #self.connect('tiploss', 'powercurve.tiploss')
        #self.connect('hubloss', 'powercurve.hubloss')
        #self.connect('wakerotation', 'powercurve.wakerotation')
        #self.connect('usecd', 'powercurve.usecd')

        # # connectiosn to tipspeed
        # self.connect('geom.R', 'tipspeed.R')
        # self.connect('max_tip_speed', 'tipspeed.Vtip_max')
        # self.connect('tipspeed.Omega_max', 'control_maxOmega')
        
        # connections to powercurve
        self.connect('drivetrainType', 'powercurve.drivetrainType')
        self.connect('drivetrainEff', 'powercurve.drivetrainEff')
        self.connect('control_Vin', 'powercurve.control_Vin')
        self.connect('control_Vout', 'powercurve.control_Vout')
        self.connect('control_maxTS', 'powercurve.control_maxTS')
        self.connect('control_maxOmega', 'powercurve.control_maxOmega')
        self.connect('control_minOmega', 'powercurve.control_minOmega')
        self.connect('control_pitch', 'powercurve.control_pitch')
        self.connect('machine_rating', 'powercurve.control_ratedPower')
        self.connect('control_tsr', 'powercurve.control_tsr')

        # connections to wind
        # self.connect('cdf_reference_mean_wind_speed', 'wind.Uref')
        self.connect('turbineclass.V_mean', 'wind.Uref')
        self.connect('wind_reference_height', 'wind.zref')
        self.connect('wind_zvec', 'wind.z')
        #self.connect('shearExp', 'wind.shearExp')

        # connections to cdf
        self.connect('powercurve.V_spline', 'cdf.x')
        self.connect('wind.U', 'cdf.xbar', src_indices=[0])
        self.connect('shape_parameter', 'cdf.k')

        # connections to aep
        self.connect('cdf.F', 'aep.CDF_V')
        self.connect('powercurve.P_spline', 'aep.P')
        self.connect('AEP_loss_factor', 'aep.lossFactor')

        # connect to outputs
        self.connect('geom.diameter', 'diameter_in')
        self.connect('turbineclass.V_extreme50', 'V_extreme_in')
        self.connect('powercurve.V', 'V_in')
        self.connect('powercurve.P', 'P_in')
        self.connect('aep.AEP', 'AEP_in')
        self.connect('powercurve.rated_V', 'rated_V_in')
        self.connect('powercurve.rated_Omega', 'rated_Omega_in')
        self.connect('powercurve.rated_pitch', 'rated_pitch_in')
        self.connect('powercurve.rated_T', 'rated_T_in')
        self.connect('powercurve.rated_Q', 'rated_Q_in')


if __name__ == '__main__':
    
    # myref = NREL5MW()
    myref = TUM3_35MW()
    # myref = DTU10MW()
    
    rotor = Problem()
    npts_coarse_power_curve = 20    # (Int): number of points to evaluate aero analysis at
    npts_spline_power_curve = 2000  # (Int): number of points to use in fitting spline to power curve
    regulation_reg_II5      = False  # calculate Region 2.5 pitch schedule, False will not maximize power in region 2.5
    regulation_reg_III      = False  # calculate Region 3 pitch schedule, False will return erroneous Thrust, Torque, and Moment for above rated
    
    rotor.model = RotorAeroPower(RefBlade=myref,
                                 npts_coarse_power_curve=npts_coarse_power_curve,
                                 npts_spline_power_curve=npts_spline_power_curve,
                                 regulation_reg_II5=regulation_reg_II5,
                                 regulation_reg_III=regulation_reg_III,
                                 topLevelFlag=True)
    
    #rotor.setup(check=False)
    rotor.setup()
    
    # === blade grid ===
    rotor['hubFraction'] = myref.hubFraction #0.025  # (Float): hub location as fraction of radius
    rotor['bladeLength'] = myref.bladeLength #61.5  # (Float, m): blade length (if not precurved or swept) otherwise length of blade before curvature
    # rotor['delta_bladeLength'] = 0.0  # (Float, m): adjustment to blade length to account for curvature from loading
    rotor['precone'] = myref.precone #2.5  # (Float, deg): precone angle
    rotor['tilt'] = myref.tilt #5.0  # (Float, deg): shaft tilt
    rotor['yaw'] = 0.0  # (Float, deg): yaw error
    rotor['nBlades'] = myref.nBlades #3  # (Int): number of blades
    # ------------------
    
    # === blade geometry ===
    rotor['r_max_chord'] = myref.r_max_chord #0.23577  # (Float): location of max chord on unit radius
    rotor['chord_in'] = myref.chord #np.array([3.2612, 4.5709, 3.3178, 1.4621])  # (Array, m): chord at control points. defined at hub, then at linearly spaced locations from r_max_chord to tip
    rotor['theta_in'] = myref.theta #np.array([13.2783, 7.46036, 2.89317, -0.0878099])  # (Array, deg): twist at control points.  defined at linearly spaced locations from r[idx_cylinder] to tip
    rotor['precurve_in'] = myref.precurve #np.array([0.0, 0.0, 0.0])  # (Array, m): precurve at control points.  defined at same locations at chord, starting at 2nd control point (root must be zero precurve)
    rotor['presweep_in'] = myref.presweep #np.array([0.0, 0.0, 0.0])  # (Array, m): precurve at control points.  defined at same locations at chord, starting at 2nd control point (root must be zero precurve)
    # rotor['delta_precurve_in'] = np.array([0.0, 0.0, 0.0])  # (Array, m): adjustment to precurve to account for curvature from loading
    rotor['sparT_in'] = myref.spar_thickness #np.array([0.05, 0.047754, 0.045376, 0.031085, 0.0061398])  # (Array, m): spar cap thickness parameters
    rotor['teT_in'] = myref.te_thickness #np.array([0.1, 0.09569, 0.06569, 0.02569, 0.00569])  # (Array, m): trailing-edge thickness parameters
    # ------------------
    
    # === atmosphere ===
    rotor['rho'] = 1.225  # (Float, kg/m**3): density of air
    rotor['mu'] = 1.81206e-5  # (Float, kg/m/s): dynamic viscosity of air
    rotor['hubHt'] = myref.hubHt #90.0
    rotor['shearExp'] = 0.0  # (Float): shear exponent
    rotor['turbine_class'] = myref.turbine_class #TURBINE_CLASS['I']  # (Enum): IEC turbine class
    rotor['wind_reference_height'] = myref.hubHt #90.0  # (Float): reference hub height for IEC wind speed (used in CDF calculation)
    # ----------------------
    
    # === control ===
    rotor['control_Vin'] = myref.control_Vin #3.0  # (Float, m/s): cut-in wind speed
    rotor['control_Vout'] = myref.control_Vout #25.0  # (Float, m/s): cut-out wind speed
    rotor['machine_rating'] = myref.rating #5e6  # (Float, W): rated power
    rotor['control_minOmega'] = myref.control_minOmega #0.0  # (Float, rpm): minimum allowed rotor rotation speed
    rotor['control_maxOmega'] = myref.control_maxOmega #12.0  # (Float, rpm): maximum allowed rotor rotation speed
    rotor['control_maxTS'] = myref.control_maxTS
    rotor['control_tsr'] = myref.control_tsr #7.55  # (Float): tip-speed ratio in Region 2 (should be optimized externally)
    rotor['control_pitch'] = myref.control_pitch #0.0  # (Float, deg): pitch angle in region 2 (and region 3 for fixed pitch machines)
    # ----------------------

    # === aero and structural analysis options ===
    rotor['nSector'] = 4  # (Int): number of sectors to divide rotor face into in computing thrust and power
    rotor['AEP_loss_factor'] = 1.0  # (Float): availability and other losses (soiling, array, etc.)
    rotor['drivetrainType'] = myref.drivetrain #'GEARED'  # (Enum)
    # ----------------------

    # === run and outputs ===
    rotor.run_driver()

    print('AEP =', rotor['AEP'])
    print('diameter =', rotor['diameter'])
    print('ratedConditions.V =', rotor['rated_V'])
    print('ratedConditions.Omega =', rotor['rated_Omega'])
    print('ratedConditions.pitch =', rotor['rated_pitch'])
    print('ratedConditions.T =', rotor['rated_T'])
    print('ratedConditions.Q =', rotor['rated_Q'])
    

    
    import matplotlib.pyplot as plt
    plt.figure()
    plt.plot(rotor['V'], rotor['P']/1e6)
    plt.xlabel('wind speed (m/s)')
    plt.xlabel('power (W)')
    
    plt.figure()
    plt.plot(rotor['V'], rotor['powercurve.pitch'])
    plt.xlabel('wind speed (m/s)')
    plt.xlabel('pitch (deg)')
    
    plt.figure()
    plt.plot(rotor['V'], rotor['powercurve.Omega'])
    plt.xlabel('wind speed (m/s)')
    plt.xlabel('omega (rpm)')
    
    plt.show()
    
    