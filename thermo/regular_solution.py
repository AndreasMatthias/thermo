# -*- coding: utf-8 -*-
'''Chemical Engineering Design Library (ChEDL). Utilities for process modeling.
Copyright (C) 2019, 2020 Caleb Bell <Caleb.Andrew.Bell@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

This module contains a class :obj:`RegularSolution` for performing activity coefficient
calculations with the regular solution model.

For reporting bugs, adding feature requests, or submitting pull requests,
please use the `GitHub issue tracker <https://github.com/CalebBell/thermo/>`_.

.. contents:: :local:

Regular Solution Class
======================

.. autoclass:: RegularSolution
    :members: to_T_xs, GE, dGE_dT, d2GE_dT2, d3GE_dT3, d2GE_dTdxs, dGE_dxs, d2GE_dxixjs, d3GE_dxixjxks
    :undoc-members:
    :show-inheritance:
    :exclude-members:

Regular Solution Regression Calculations
========================================
.. autofunction:: regular_solution_gammas_binaries

'''

from __future__ import division
from fluids.numerics import numpy as np, trunc_exp
from thermo.activity import GibbsExcess
from chemicals.utils import exp, log
from fluids.constants import R, R_inv

try:
    array, zeros, npsum = np.array, np.zeros, np.sum
except (ImportError, AttributeError):
    pass

__all__ = ['RegularSolution', 'regular_solution_gammas', 
           'regular_solution_gammas_binaries',
           'regular_solution_gammas_binaries_jac']


def regular_solution_Hi_sums(SPs, Vs, xsVs, coeffs, N, Hi_sums=None):
    if Hi_sums is None:
        Hi_sums = [0.0]*N
    for i in range(N):
        t = 0.0
        for j in range(N):
            # Hi does not depend on composition at all and can be stored as a matrix.
            SPi_m_SPj = SPs[i] - SPs[j]
            Hi = SPs[i]*SPs[j]*(coeffs[i][j] + coeffs[j][i]) + SPi_m_SPj*SPi_m_SPj
            t += xsVs[j]*Hi
        Hi_sums[i] = Vs[i]*t
    return Hi_sums


def regular_solution_GE(SPs, xsVs, coeffs, N, xsVs_sum_inv):
    # This can have its speed improved
    num = 0.0
    for i in range(N):
        coeffsi = coeffs[i]
        tot = 0.0
        for j in range(N):
            SPi_m_SPj = SPs[i] - SPs[j]
            tot += xsVs[j]*SPi_m_SPj*SPi_m_SPj
        tot *= 0.5

        tot2 = 0.0
        for j in range(N):
            # could facot out a the  xsVs[j]*SPs[j] into a single term
            tot2 += xsVs[j]*SPs[j]*coeffsi[j]
        num += (tot + tot2*SPs[i])*xsVs[i]
    GE = num*xsVs_sum_inv
    return GE


def regular_solution_dGE_dxs(Vs, Hi_sums, N, xsVs_sum_inv, GE, dGE_dxs=None):
    if dGE_dxs is None:
        dGE_dxs = [0.0]*N
    for i in range(N):
        # i is what is being differentiated
        dGE_dxs[i] = (Hi_sums[i] - GE*Vs[i])*xsVs_sum_inv
    return dGE_dxs

def regular_solution_gammas(T, xs, Vs, SPs, lambda_coeffs, N, 
                            xsVs=None, Hi_sums=None, dGE_dxs=None,
                            gammas=None):
    if xsVs is None:
        xsVs = [0.0]*N
    
    for i in range(N):
        xsVs[i] = xs[i]*Vs[i]
    
    xsVs_sum = 0.0
    for i in range(N):
        xsVs_sum += xsVs[i]
    xsVs_sum_inv = 1.0/xsVs_sum
    
    if Hi_sums is None:
        Hi_sums = [0.0]*N
    
    Hi_sums = regular_solution_Hi_sums(SPs=SPs, Vs=Vs, xsVs=xsVs, coeffs=lambda_coeffs,
                                       N=N, Hi_sums=Hi_sums)
    GE = regular_solution_GE(SPs=SPs, xsVs=xsVs, coeffs=lambda_coeffs, N=N, xsVs_sum_inv=xsVs_sum_inv)
    
    if dGE_dxs is None:
        dGE_dxs = [0.0]*N
    dG_dxs = regular_solution_dGE_dxs(Vs=Vs, Hi_sums=Hi_sums, N=N, xsVs_sum_inv=xsVs_sum_inv,
                                      GE=GE, dGE_dxs=dGE_dxs)
    xdx_totF = GE
    for i in range(N):
        xdx_totF -= xs[i]*dG_dxs[i]
    
    if gammas is None:
        gammas = [0.0]*N
    
    for i in range(N):
        gammas[i] = dG_dxs[i] + xdx_totF
    RT_inv = 1.0/(R*T)
    for i in range(N):
        gammas[i] *= RT_inv
    for i in range(N):
        gammas[i] = exp(gammas[i])
    return gammas


def regular_solution_d2GE_dxixjs(Vs, SPs, Hi_sums, dGE_dxs, N, GE, coeffs, xsVs_sum_inv, d2GE_dxixjs=None):
    if d2GE_dxixjs is None:
        d2GE_dxixjs = [[0.0]*N for i in range(N)] # numba: delete
#        d2GE_dxixjs = zeros((N, N)) # numba: uncomment

    for i in range(N):
        row = d2GE_dxixjs[i]
        v0 = (Vs[i]*GE - Hi_sums[i])*xsVs_sum_inv*xsVs_sum_inv
        v1 = Vs[i]*xsVs_sum_inv
        for j in range(N):
            SPi_m_SPj = SPs[i] - SPs[j]
            Hi = SPs[i]*SPs[j]*(coeffs[i][j] + coeffs[j][i]) + SPi_m_SPj*SPi_m_SPj
            tot = Vs[j]*v0 + v1*(Vs[j]*Hi - dGE_dxs[j])

            row[j] = tot
    return d2GE_dxixjs

def regular_solution_d3GE_dxixjxks(Vs, SPs, Hi_sums, dGE_dxs, N, GE, xsVs_sum_inv, d2GE_dxixjs, coeffs,
                                   d3GE_dxixjxks=None):
    if d3GE_dxixjxks is None:
        d3GE_dxixjxks = [[[0.0]*N for _ in range(N)] for _ in range(N)] # numba: delete
#        d3GE_dxixjxks = zeros((N, N, N)) # numba: uncomment

    # all the same: analytical[i][j][k] = analytical[i][k][j] = analytical[j][i][k] = analytical[j][k][i] = analytical[k][i][j] = analytical[k][j][i] = float(v)
    for i in range(N):
        dG_matrix = d3GE_dxixjxks[i]
        for j in range(N):
            dG_row = dG_matrix[j]
            for k in range(N):
                tot = 0.0
                thirds = -2.0*Vs[i]*Vs[j]*Vs[k]*GE + 2.0*Vs[j]*Vs[k]*Hi_sums[i]
                seconds = Vs[i]*(Vs[j]*dGE_dxs[k] + Vs[k]*dGE_dxs[j])
                seconds -= Vs[i]*Vs[j]*Vs[k]*(
                            SPs[i]*(SPs[j]*(coeffs[i][j] + coeffs[j][i]) + SPs[k]*(coeffs[i][k] + coeffs[k][i]))
                             + (SPs[i]-SPs[j])**2 + (SPs[i] - SPs[k])**2
                             )
                firsts = -Vs[i]*d2GE_dxixjs[j][k]



                tot = firsts*xsVs_sum_inv + seconds*xsVs_sum_inv*xsVs_sum_inv + thirds*xsVs_sum_inv*xsVs_sum_inv*xsVs_sum_inv
                dG_row[k] = tot
    return d3GE_dxixjxks


class RegularSolution(GibbsExcess):
    r'''Class for representing an a liquid with excess gibbs energy represented
    by the Regular Solution model. This model is not temperature dependent and
    has limited predictive ability, but can be used without interaction
    parameters. This model is described in [1]_.

    .. math::
        G^E = \frac{\sum_m \sum_n (x_m x_n V_m V_n A_{mn})}{\sum_m x_m V_m}

    .. math::
        A_{mn} = 0.5(\delta_m - \delta_n)^2 - \delta_m \delta_n k_{mn}

    In the above equation, :math:`\delta` represents the solubility parameters,
    and :math:`k_{mn}` is the interaction coefficient between `m` and `n`.
    The model makes no assumption about the symmetry of this parameter.

    Parameters
    ----------
    T : float
        Temperature, [K]
    xs : list[float]
        Mole fractions, [-]
    Vs : list[float]
        Molar volumes of each compond at a reference temperature (often 298.15
        K), [m^3/mol]
    SPs : list[float]
        Solubility parameters of each compound; normally at a reference
        temperature of 298.15 K, [Pa^0.5]
    lambda_coeffs : list[list[float]], optional
        Optional interaction parameters, [-]

    Attributes
    ----------
    T : float
        Temperature, [K]
    xs : list[float]
        Mole fractions, [-]
    Vs : list[float]
        Molar volumes of each compond at a reference temperature (often 298.15
        K), [K]
    SPs : list[float]
        Solubility parameters of each compound; normally at a reference
        temperature of 298.15 K, [Pa^0.5]
    lambda_coeffs : list[list[float]]
        Interaction parameters, [-]

    Notes
    -----
    In addition to the methods presented here, the methods of its base class
    :obj:`thermo.activity.GibbsExcess` are available as well.
    
    Additional equations of note are as follows.
    
    .. math::
        G^E = H^E
    
    .. math::
        S^E = 0
        
    .. math::
        \delta = \sqrt{\frac{\Delta H_{vap} - RT}{V_m}}

    Examples
    --------
    **Example 1**
    
    From [2]_, calculate the activity coefficients at infinite dilution for the
    system benzene-cyclohexane at 253.15 K using the regular solution model
    (example 5.20, with unit conversion in-line):

    >>> from scipy.constants import calorie
    >>> GE = RegularSolution(T=353.15, xs=[.5, .5], Vs=[89E-6, 109E-6], SPs=[9.2*(calorie*1e6)**0.5, 8.2*(calorie*1e6)**0.5])
    >>> GE.gammas_infinite_dilution()
    [1.1352128394, 1.16803058378]

    This matches the solution given of [1.135, 1.168].
    
    **Example 2**
    
    Benzene and cyclohexane calculation from [3]_, without interaction
    parameters.
    
    >>> GE = RegularSolution(T=353, xs=[0.01, 0.99], Vs=[8.90e-05, 1.09e-04], SPs=[9.2*(calorie/1e-6)**0.5, 8.2*(calorie/1e-6)**0.5])
    >>> GE.gammas()
    [1.1329295, 1.00001039]
    
    
    **Example 3**
    
    Another common model is the Flory-Huggins model. This isn't implemented 
    as a separate model, but it is possible to modify the activity coefficient
    results of :obj:`RegularSolution` to obtain the activity coefficients from
    the Flory-Huggins model anyway. ChemSep [4]_ implements the Flory-Huggins model
    and calls it the regular solution model, so results can't be compared with
    ChemSep except when making the following manual solution. The example below
    uses parameters from ChemSep for ethanol and water.
        
    >>> GE = RegularSolution(T=298.15, xs=[0.5, 0.5], Vs=[0.05868e-3, 0.01807e-3], SPs=[26140.0, 47860.0])
    >>> GE.gammas() # Regular solution activity coefficients
    [1.8570955489, 7.464567232]
    >>> lngammass = [log(g) for g in GE.gammas()]
    >>> thetas = [GE.Vs[i]/sum(GE.xs[i]*GE.Vs[i] for i in range(GE.N)) for i in range(GE.N)]
    >>> gammas_flory_huggins = [exp(lngammass[i] + log(thetas[i]) + 1 - thetas[i]) for i in range(GE.N)]
    >>> gammas_flory_huggins
    [1.672945693, 5.9663471]
    
    This matches the values calculated from ChemSep exactly.

    References
    ----------
    .. [1] Poling, Bruce E., John M. Prausnitz, and John P. O’Connell. The
       Properties of Gases and Liquids. 5th edition. New York: McGraw-Hill
       Professional, 2000.
    .. [2] Gmehling, Jürgen, Michael Kleiber, Bärbel Kolbe, and Jürgen Rarey.
       Chemical Thermodynamics for Process Simulation. John Wiley & Sons, 2019.
    .. [3] Elliott, J., and Carl Lira. Introductory Chemical Engineering 
       Thermodynamics. 2nd edition. Upper Saddle River, NJ: Prentice Hall, 2012.
    .. [4] Kooijman, Harry A., and Ross Taylor. The ChemSep Book. Books on 
       Demand Norderstedt, Germany, 2000.
    '''
    model_id = 400

    def __init__(self, T, xs, Vs, SPs, lambda_coeffs=None):
        # lambda_coeffs is N*N of zeros for no interaction parameters
        self.T = T
        self.xs = xs
        self.Vs = Vs
        self.SPs = SPs
        self.N = N = len(Vs)
        self.scalar = scalar = type(Vs) is list

        if lambda_coeffs is None:
            if scalar:
                lambda_coeffs = [[0.0]*N for i in range(N)]
            else:
                lambda_coeffs = zeros((N, N))
        self.lambda_coeffs = lambda_coeffs
        
        lambda_coeffs_zero = True
        for i in range(N):
            r = lambda_coeffs[i]
            for j in range(N):
                if r[j] != 0.0:
                    lambda_coeffs_zero = False
                    break
            if not lambda_coeffs_zero:
                break
        self._lambda_coeffs_zero = lambda_coeffs_zero

        if scalar:
            xsVs = []
            xsVs_sum = 0.0
            for i in range(N):
                xV = xs[i]*Vs[i]
                xsVs_sum += xV
                xsVs.append(xV)

        else:
            xsVs =  (xs*Vs)
            xsVs_sum = xsVs.sum()

        self.xsVs = xsVs
        self.xsVs_sum = xsVs_sum
        self.xsVs_sum_inv = 1.0/xsVs_sum

    _model_attributes = ('Vs', 'SPs', 'lambda_coeffs')

    def __repr__(self):
        s = '%s(T=%s, xs=%s, Vs=%s, SPs=%s' %(self.__class__.__name__, repr(self.T), repr(self.xs),
                self.Vs, self.SPs)
        if not self._lambda_coeffs_zero:
            s += ' , lambda_coeffs=%s)' %(self.lambda_coeffs,)
        else:
            s += ')'
        
        return s

    def to_T_xs(self, T, xs):
        r'''Method to construct a new :obj:`RegularSolution` instance at
        temperature `T`, and mole fractions `xs`
        with the same parameters as the existing object.

        Parameters
        ----------
        T : float
            Temperature, [K]
        xs : list[float]
            Mole fractions of each component, [-]

        Returns
        -------
        obj : RegularSolution
            New :obj:`RegularSolution` object at the specified conditions [-]

        Notes
        -----
        '''
        new = self.__class__.__new__(self.__class__)
        new.T = T
        new.xs = xs
        new.SPs = self.SPs
        new.Vs = Vs = self.Vs
        new.N = N = self.N
        new.lambda_coeffs = self.lambda_coeffs
        new._lambda_coeffs_zero = self._lambda_coeffs_zero
        new.scalar = scalar = self.scalar

        if scalar:
            xsVs = []
            xsVs_sum = 0.0
            for i in range(N):
                xV = xs[i]*Vs[i]
                xsVs_sum += xV
                xsVs.append(xV)
        else:
            xsVs = xs*Vs
            xsVs_sum = float(npsum(xsVs))
        new.xsVs = xsVs
        new.xsVs_sum = xsVs_sum
        new.xsVs_sum_inv = 1.0/xsVs_sum
        return new


    def GE(self):
        r'''Calculate and return the excess Gibbs energy of a liquid phase
        using the regular solution model.

        .. math::
            G^E = \frac{\sum_m \sum_n (x_m x_n V_m V_n A_{mn})}{\sum_m x_m V_m}

        .. math::
            A_{mn} = 0.5(\delta_m - \delta_n)^2 - \delta_m \delta_n k_{mn}

        Returns
        -------
        GE : float
            Excess Gibbs energy, [J/mol]

        Notes
        -----
        '''
        '''
        from sympy import *
        GEvar, dGEvar_dT, GEvar_dx, dGEvar_dxixj, H = symbols("GEvar, dGEvar_dT, GEvar_dx, dGEvar_dxixj, H", cls=Function)

        N = 3
        cmps = range(N)
        R, T = symbols('R, T')
        xs = x0, x1, x2 = symbols('x0, x1, x2')
        Vs = V0, V1, V2 = symbols('V0, V1, V2')
        SPs = SP0, SP1, SP2 = symbols('SP0, SP1, SP2')
        l00, l01, l02, l10, l11, l12, l20, l21, l22 = symbols('l00, l01, l02, l10, l11, l12, l20, l21, l22')
        l_ijs = [[l00, l01, l02],
                 [l10, l11, l12],
                 [l20, l21, l22]]

        GE = 0
        denom = sum([xs[i]*Vs[i] for i in cmps])
        num = 0
        for i in cmps:
            for j in cmps:
                Aij = (SPs[i] - SPs[j])**2/2 + l_ijs[i][j]*SPs[i]*SPs[j]
                num += xs[i]*xs[j]*Vs[i]*Vs[j]*Aij
        GE = num/denom
        '''
        try:
            return self._GE
        except AttributeError:
            pass
        GE = self._GE = regular_solution_GE(self.SPs, self.xsVs, self.lambda_coeffs, self.N, self.xsVs_sum_inv)
        return GE


    def dGE_dxs(self):
        r'''Calculate and return the mole fraction derivatives of excess Gibbs
        energy of a liquid phase using the regular solution model.

        .. math::
            \frac{\partial G^E}{\partial x_i} = \frac{-V_i G^E + \sum_m V_i V_m
            x_m[\delta_i\delta_m(k_{mi} + k_{im}) + (\delta_i - \delta_m)^2 ]}
            {\sum_m V_m x_m}

        Returns
        -------
        dGE_dxs : list[float]
            Mole fraction derivatives of excess Gibbs energy, [J/mol]

        Notes
        -----
        '''
        '''
        dGEdxs = (diff(GE, x0)).subs(GE, GEvar(x0, x1, x2))
        Hi = dGEdxs.args[0].args[1]
        dGEdxs
        '''
        try:
            return self._dGE_dxs
        except AttributeError:
            pass
        try:
            GE = self._GE
        except:
            GE = self.GE()

        if self.scalar:
            dGE_dxs = [0.0]*self.N
        else:
            dGE_dxs = zeros(self.N)

        regular_solution_dGE_dxs(self.Vs, self.Hi_sums(), self.N, self.xsVs_sum_inv, GE, dGE_dxs)
        self._dGE_dxs = dGE_dxs
        return dGE_dxs

    def Hi_sums(self):
        try:
            return self._Hi_sums
        except:
            pass
        if self.scalar:
            Hi_sums = [0.0]*self.N
        else:
            Hi_sums = zeros(self.N)

        regular_solution_Hi_sums(self.SPs, self.Vs, self.xsVs, self.lambda_coeffs, self.N, Hi_sums)
        self._Hi_sums = Hi_sums
        return Hi_sums

    def d2GE_dxixjs(self):
        r'''Calculate and return the second mole fraction derivatives of excess
        Gibbs energy of a liquid phase using the regular solution model.

        .. math::
            \frac{\partial^2 G^E}{\partial x_i \partial x_j} = \frac{V_j(V_i G^E - H_{ij})}{(\sum_m V_m x_m)^2}
            - \frac{V_i \frac{\partial G^E}{\partial x_j}}{\sum_m V_m x_m}
            + \frac{V_i V_j[\delta_i\delta_j(k_{ji} + k_{ij}) + (\delta_i - \delta_j)^2] }{\sum_m V_m x_m}

        Returns
        -------
        d2GE_dxixjs : list[list[float]]
            Second mole fraction derivatives of excess Gibbs energy, [J/mol]

        Notes
        -----
        '''
        '''
        d2GEdxixjs = diff((diff(GE, x0)).subs(GE, GEvar(x0, x1, x2)), x1).subs(Hi, H(x0, x1, x2))
        d2GEdxixjs
        '''
        try:
            return self._d2GE_dxixjs
        except AttributeError:
            pass
        try:
            GE = self._GE
        except:
            GE = self.GE()
        try:
            dGE_dxs = self._dGE_dxs
        except:
            dGE_dxs = self.dGE_dxs()
        N = self.N

        if self.scalar:
            d2GE_dxixjs = [[0.0]*N for i in range(N)]
        else:
            d2GE_dxixjs = zeros((N, N))

        try:
            Hi_sums = self._Hi_sums
        except:
            Hi_sums = self.Hi_sums()

        d2GE_dxixjs = regular_solution_d2GE_dxixjs(self.Vs, self.SPs, Hi_sums, dGE_dxs, N, GE, self.lambda_coeffs,
                                                   self.xsVs_sum_inv, d2GE_dxixjs)
        self._d2GE_dxixjs = d2GE_dxixjs
        return d2GE_dxixjs

    def d3GE_dxixjxks(self):
        r'''Calculate and return the third mole fraction derivatives of excess
        Gibbs energy.

        .. math::
            \frac{\partial^3 G^E}{\partial x_i \partial x_j \partial x_k} = \frac{-2V_iV_jV_k G^E + 2 V_j V_k H_{ij}} {(\sum_m V_m x_m)^3}
            + \frac{V_i\left(V_j\frac{\partial G^E}{\partial x_k} + V_k\frac{\partial G^E}{\partial x_j}  \right)} {(\sum_m V_m x_m)^2}
            - \frac{V_i \frac{\partial^2 G^E}{\partial x_j \partial x_k}}{\sum_m V_m x_m}
            - \frac{V_iV_jV_k[\delta_i(\delta_j(k_{ij} + k_{ji}) + \delta_k(k_{ik} + k_{ki})) + (\delta_i - \delta_j)^2 + (\delta_i - \delta_k)^2 ]}{(\sum_m V_m x_m)^2}

        Returns
        -------
        d3GE_dxixjxks : list[list[list[float]]]
            Third mole fraction derivatives of excess Gibbs energy, [J/mol]

        Notes
        -----
        '''
        try:
            return self._d3GE_dxixjxks
        except:
            pass
        N = self.N
        try:
            GE = self._GE
        except:
            GE = self.GE()
        try:
            dGE_dxs = self._dGE_dxs
        except:
            dGE_dxs = self.dGE_dxs()
        try:
            d2GE_dxixjs = self._d2GE_dxixjs
        except:
            d2GE_dxixjs = self.d2GE_dxixjs()
        try:
            Hi_sums = self._Hi_sums
        except:
            Hi_sums = self.Hi_sums()

        if self.scalar:
            d3GE_dxixjxks = [[[0.0]*N for _ in range(N)] for _ in range(N)]
        else:
            d3GE_dxixjxks = zeros((N, N, N))

        d3GE_dxixjxks = regular_solution_d3GE_dxixjxks(self.Vs, self.SPs, Hi_sums, dGE_dxs, self.N, GE,
                                                       self.xsVs_sum_inv, d2GE_dxixjs, self.lambda_coeffs,
                                                       d3GE_dxixjxks)
        self._d3GE_dxixjxks = d3GE_dxixjxks
        return d3GE_dxixjxks

    def d2GE_dTdxs(self):
        r'''Calculate and return the temperature derivative of mole fraction
        derivatives of excess Gibbs energy.

        .. math::
            \frac{\partial^2 g^E}{\partial x_i \partial T} = 0

        Returns
        -------
        d2GE_dTdxs : list[float]
            Temperature derivative of mole fraction derivatives of excess Gibbs
            energy, [J/(mol*K)]

        Notes
        -----
        '''
        if self.scalar:
            return [0.0]*self.N
        return zeros(self.N)

    def dGE_dT(self):
        r'''Calculate and return the temperature derivative of excess Gibbs
        energy of a liquid phase.

        .. math::
            \frac{\partial g^E}{\partial T} = 0

        Returns
        -------
        dGE_dT : float
            First temperature derivative of excess Gibbs energy, [J/(mol*K)]

        Notes
        -----
        '''
        return 0.0

    def d2GE_dT2(self):
        r'''Calculate and return the second temperature derivative of excess
        Gibbs energy of a liquid phas.

        .. math::
            \frac{\partial^2 g^E}{\partial T^2} = 0

        Returns
        -------
        d2GE_dT2 : float
            Second temperature derivative of excess Gibbs energy, [J/(mol*K^2)]

        Notes
        -----
        '''
        return 0.0

    def d3GE_dT3(self):
        r'''Calculate and return the third temperature derivative of excess
        Gibbs energy of a liquid phase.

        .. math::
            \frac{\partial^3 g^E}{\partial T^3} = 0

        Returns
        -------
        d3GE_dT3 : float
            Third temperature derivative of excess Gibbs energy, [J/(mol*K^3)]

        Notes
        -----
        '''
        return 0.0


    @classmethod
    def regress_binary_parameters(cls, gammas, xs, Vs, SPs, Ts, symmetric=False,
                                  use_numba=False,
                                  do_statistics=True, **kwargs):
        # Load the functions either locally or with numba
        if use_numba:
            from thermo.numba import regular_solution_gammas_binaries as work_func, regular_solution_gammas_binaries_jac as jac_func
            Vs, SPs, Ts = array(Vs), array(SPs), array(Ts)
        else:
            work_func = regular_solution_gammas_binaries
            jac_func = regular_solution_gammas_binaries_jac
        
        # Allocate all working memory
        pts = len(xs)
        gammas_iter = zeros(pts*2)
        jac_iter = zeros((pts*2, 2))

        # Plain objective functions
        if symmetric:
            def fitting_func(xs, lambda12):
                return work_func(xs, Vs, SPs, Ts, lambda12, lambda12, gammas_iter)
            
            def analytical_jac(xs, lambda12):
                return jac_func(xs, Vs, SPs, Ts, lambda12, lambda12, jac_iter).sum(axis=1)
    
        else:
            def fitting_func(xs, lambda12, lambda21):
                return work_func(xs, Vs, SPs, Ts, lambda12, lambda21, gammas_iter)
            
            def analytical_jac(xs, lambda12, lambda21):
                return jac_func(xs, Vs, SPs, Ts, lambda12, lambda21, jac_iter)
    
        # The extend calls has been tested to be the fastest compared to numpy and list comprehension
        xs_working = []
        for xsi in xs:
            xs_working.extend(xsi)
        gammas_working = []
        for gammasi in gammas:
            gammas_working.extend(gammasi)
            
        xs_working = array(xs_working)
        gammas_working = array(gammas_working)
        
        # Objective functions for leastsq maximum speed
        if symmetric:
            def func_wrapped_for_leastsq(params):
                return work_func(xs_working, Vs, SPs, Ts, params[0], params[0], gammas_iter) - gammas_working
    
            def jac_wrapped_for_leastsq(params):
                return jac_func(xs_working, Vs, SPs, Ts, params[0], params[0], jac_iter).sum(axis=1)
        
        else:
            def func_wrapped_for_leastsq(params):
                return work_func(xs_working, Vs, SPs, Ts, params[0], params[1], gammas_iter) - gammas_working
    
            def jac_wrapped_for_leastsq(params):
                return jac_func(xs_working, Vs, SPs, Ts, params[0], params[1], jac_iter)
        
        if symmetric:
            use_fit_parameters = ['lambda12']
        else:
            use_fit_parameters = ['lambda12', 'lambda21']
        return GibbsExcess._regress_binary_parameters(gammas_working, xs_working, fitting_func=fitting_func,
                                                      fit_parameters=use_fit_parameters,
                                                      use_fit_parameters=use_fit_parameters,
                                                      initial_guesses=cls._gamma_parameter_guesses,
                                                       analytical_jac=jac_func,
                                                      use_numba=use_numba,
                                                      do_statistics=do_statistics,
                                                      func_wrapped_for_leastsq=func_wrapped_for_leastsq,
                                                       jac_wrapped_for_leastsq=jac_wrapped_for_leastsq,
                                                      **kwargs)
    _gamma_parameter_guesses = [#{'lambda12': 1.0, 'lambda21': 1.0}, # 1 is always tried!
                                {'lambda12': 1e7, 'lambda21': -1e7},
                                {'lambda12': 0.01, 'lambda21': 0.01},
                                ]
    for i in range(len(_gamma_parameter_guesses)):
        r = _gamma_parameter_guesses[i]
        if r['lambda21'] != r['lambda12']:
            _gamma_parameter_guesses.append({'lambda12': r['lambda21'], 'lambda21': r['lambda12']})
    del i, r


MIN_LAMBDA_REGULAR_SOLUTION = -1e100
MAX_LAMBDA_REGULAR_SOLUTION = 1e100

# MIN_LAMBDA_REGULAR_SOLUTION = -10.0
# MAX_LAMBDA_REGULAR_SOLUTION = 10.0

def regular_solution_gammas_binaries(xs, Vs, SPs, Ts, lambda12, lambda21, 
                                     gammas=None):
    r'''Calculates activity coefficients with the regular solution model
    at fixed `lambda` values for
    a binary system at a series of mole fractions at specified temperatures.
    This is used for 
    regression of `lambda` parameters. This function is highly optimized,
    and operates on multiple points at a time.
    
    .. math::
        \ln \gamma_1 = \frac{V_1\phi_2^2}{RT}\left[
            (\text{SP}_1-\text{SP}_2)^2 + \lambda_{12}\text{SP}_1\text{SP}_2
            + \lambda_{21}\text{SP}_1\text{SP}_2
            \right]

    .. math::
        \ln \gamma_2 =  \frac{V_2\phi_1^2}{RT}\left[
            (\text{SP}_1-\text{SP}_2)^2 + \lambda_{12}\text{SP}_1\text{SP}_2
            + \lambda_{21}\text{SP}_1\text{SP}_2
            \right]
    
    .. math::
        \phi_1 = \frac{x_1 V_1}{x_1 V_1 + x_2 V_2}

    .. math::
        \phi_2 = \frac{x_2 V_2}{x_1 V_1 + x_2 V_2}

    Parameters
    ----------
    xs : list[float]
        Liquid mole fractions of each species in the format
        x0_0, x1_0, (component 1 point1, component 2 point 1),
        x0_1, x1_1, (component 1 point2, component 2 point 2), ...
        size pts*2
        [-]
    Vs : list[float]
        Molar volumes of each of the two components, [m^3/mol]
    SPs : list[float]
        Solubility parameters of each of the two components, [Pa^0.5]
    Ts : flist[float]
        Temperatures of each composition point; half the length of `xs`, [K]
    lambda12 : float
        `lambda` parameter for 12, [-]
    lambda21 : float
        `lambda` parameter for 21, [-]
    gammas : list[float], optional
        Array to store the activity coefficient for each species in the liquid 
        mixture, indexed the same as `xs`; can be omitted or provided
        for slightly better performance [-]

    Returns
    -------
    gammas : list[float]
        Activity coefficient for each species in the liquid mixture,
        indexed the same as `xs`, [-]

    Notes
    -----
    
    Examples
    --------
    >>> regular_solution_gammas_binaries([.1, .9, 0.3, 0.7, .85, .15], Vs=[7.421e-05, 8.068e-05], SPs=[19570.2, 18864.7], Ts=[300.0, 400.0, 500.0], lambda12=0.1759, lambda21=0.7991)
    [6818.90697, 1.105437, 62.6628, 2.01184, 1.181434, 137.6232]
    '''
    if lambda12 < MIN_LAMBDA_REGULAR_SOLUTION:
        lambda12 = MIN_LAMBDA_REGULAR_SOLUTION
    if lambda21 < MIN_LAMBDA_REGULAR_SOLUTION:
        lambda21 = MIN_LAMBDA_REGULAR_SOLUTION
    if lambda12 > MAX_LAMBDA_REGULAR_SOLUTION:
        lambda12 = MAX_LAMBDA_REGULAR_SOLUTION
    if lambda21 > MAX_LAMBDA_REGULAR_SOLUTION:
        lambda21 = MAX_LAMBDA_REGULAR_SOLUTION
    pts = len(xs)//2 # Always even
    # lambda21 = lambda12
    
    if gammas is None:
        allocate_size = (pts*2)
        gammas = [0.0]*allocate_size
        
    l01, l10 = lambda12, lambda21
    SP0, SP1 = SPs
    V0, V1 = Vs
    c0 = (SP0-SP1)
    base_term = (c0*c0 + l01*SP0*SP1 + l10*SP0*SP1)*R_inv

    for i in range(pts):
        i2 = i*2
        x0 = xs[i2]
        x1 = 1.0 - x0
        
        x0V0 = x0*V0
        x1V1 = x1*V1
        den_inv = 1.0/(x0V0 + x1V1)
        phi0, phi1 = x0V0*den_inv, x1V1*den_inv
        term = base_term/(Ts[i])
        gammas[i2] = trunc_exp(V0*phi1*phi1*term)
        gammas[i2 + 1] = trunc_exp(V1*phi0*phi0*term)
    return gammas

def regular_solution_gammas_binaries_jac(xs, Vs, SPs, Ts, lambda12, lambda21, jac=None):
    if lambda12 < MIN_LAMBDA_REGULAR_SOLUTION:
        lambda12 = MIN_LAMBDA_REGULAR_SOLUTION
    if lambda21 < MIN_LAMBDA_REGULAR_SOLUTION:
        lambda21 = MIN_LAMBDA_REGULAR_SOLUTION
    if lambda12 > MAX_LAMBDA_REGULAR_SOLUTION:
        lambda12 = MAX_LAMBDA_REGULAR_SOLUTION
    if lambda21 > MAX_LAMBDA_REGULAR_SOLUTION:
        lambda21 = MAX_LAMBDA_REGULAR_SOLUTION
    pts = len(xs)//2 # Always even
    
    if jac is None:
        allocate_size = (pts*2)
        jac = np.zeros((allocate_size, 2))
        
    l01, l10 = lambda12, lambda21
    SP0, SP1 = SPs
    V0, V1 = Vs
    
    x2 = SP0*SP1
    c99 =  (SP0 - SP1)
    c100 = (l01*x2 + l10*x2 + c99*c99)
    c101 = V0*V1*V1
    c102 = V0*V0*V1
    
    for i in range(pts):
        i2 = i*2
        x0 = xs[i2]
        x1 = 1.0 - x0
        T = Ts[i]
        
        c0 = (V0*x0 + V1*x1)
        
        x3 = R_inv/(T*c0*c0)
        x4 = x3*c100
        x5 = c101*x1*x1
        x6 = x2*x3
        x7 = x5*x6*trunc_exp(x4*x5)
        x8 = c102*x0*x0
        x9 = x6*x8*trunc_exp(x4*x8)

        jac[i2][0] = x7
        jac[i2][1] = x7
        jac[i2 + 1][0] = x9 
        jac[i2 + 1][1] = x9
    return jac
