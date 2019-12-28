# -*- coding: utf-8 -*-
'''Chemical Engineering Design Library (ChEDL). Utilities for process modeling.
Copyright (C) 2016, Caleb Bell <Caleb.Andrew.Bell@gmail.com>

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
SOFTWARE.'''

from numpy.testing import assert_allclose
import pytest
from thermo.utils import normalize
from thermo.eos import *
from thermo.eos_mix import *
from scipy.misc import derivative
from fluids.constants import R
from fluids.numerics import jacobian, hessian
from scipy.optimize import minimize, newton
from math import log, exp, sqrt
from thermo import Mixture
from thermo.property_package import eos_Z_test_phase_stability, eos_Z_trial_phase_stability
import numpy as np
from thermo.property_package_constants import (PropertyPackageConstants, 
                                               NRTL_PKG, IDEAL_PKG, PR_PKG)


def test_PRMIX_quick():
    # Two-phase nitrogen-methane
    eos = PRMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])

    Vs_calc = eos.sorted_volumes
#    eos.volume_solutions(115, 1E6, eos.b, eos.delta, eos.epsilon, eos.a_alpha)
    Vs_expected = [3.6257362939705926e-05, 0.0001938347308115875, 0.0007006659231347702]
    assert_allclose(Vs_calc, Vs_expected)

    # Test of a_alphas
    a_alphas = (0.21876490011332972, -0.0006346637957108072, 3.6800265478701025e-06)
    a_alphas_fast = eos.a_alpha_and_derivatives(eos.T)
    assert_allclose(a_alphas, a_alphas_fast)
    a_alphas_slow = eos.a_alpha_and_derivatives(eos.T, quick=False)
    assert_allclose(a_alphas, a_alphas_slow)
    assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False), rtol=1e-12)

    # back calculation for T, both solutions
    for V in [3.625736293970586e-05, 0.0007006659231347704]:
        eos = PRMIX(V=V, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
        assert_allclose(eos.T, 115)
        T_slow = eos.solve_T(P=1E6, V=V, quick=False)
        assert_allclose(T_slow, 115)


    # Fugacities
    eos = PRMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(eos.phis_l, [1.5877216764229214, 0.14693710450607678])
    assert_allclose(eos.phis_g, [0.8730618494018239, 0.7162292765506479])
    assert_allclose(eos.fugacities_l, [793860.8382114634, 73468.55225303846])
    assert_allclose(eos.fugacities_g, [436530.9247009119, 358114.63827532396])
    
    # Numerically test fugacities at one point
    def numerical_fugacity_coefficient(n1, n2=0.5, switch=False, l=True):
        if switch:
            n1, n2 = n2, n1
        tot = n1+n2
        zs = [i/tot for i in [n1,n2]]
        a = PRMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=zs, kijs=[[0,0],[0,0]])
        phi = a.phi_l if l else a.phi_g
        return tot*log(phi)

    phis = [[derivative(numerical_fugacity_coefficient, 0.5, dx=1E-6, order=25, args=(0.5, i, j)) for i in [False, True]] for j in [False, True]]
    assert_allclose(phis, [eos.lnphis_g, eos.lnphis_l])

    # Gas phase only test point
    a = PRMIX(T=300, P=1E7, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(a.phis_g, [0.9855336740251448, 0.8338953860988254]) # Both models.
    assert_allclose(a.phis_g, [0.9855, 0.8339], rtol=1E-4) # Calculated with thermosolver V1
    
    # Test against PrFug.xlsx
    # chethermo (Elliott, Richard and Lira, Carl T. - 2012 - Introductory Chemical Engineering Thermodynamics)
    kijs = [[0, 0.00076, 0.00171], [0.00076, 0, 0.00061], [0.00171, 0.00061, 0]]
    e = PRMIX(Tcs=[469.7, 507.4, 540.3], zs=[0.8168, 0.1501, 0.0331], 
              omegas=[0.249, 0.305, 0.349], Pcs=[3.369E6, 3.012E6, 2.736E6],
              T=322.29, P=101325, kijs=kijs)
    assert_allclose(e.V_g, 0.025451314884217785)
    assert_allclose(e.V_l, 0.00012128151502941696)
    
    assert_allclose(e.fugacity_g, 97639.120236046)
    assert_allclose(e.fugacity_l, 117178.31044886599, rtol=5E-5)
    
    assert_allclose(e.fugacities_g, [79987.657739064, 14498.518199677, 3155.0680076450003])
    assert_allclose(e.fugacities_l, [120163.95699262699, 7637.916974562, 620.954835936], rtol=5E-5)
    
    assert_allclose(e.phis_g, [0.966475030274237, 0.953292801077091, 0.940728104174207])
    assert_allclose(e.phis_l, [1.45191729893103, 0.502201064053298, 0.185146457753801], rtol=1E-4)
    
    
    # CH4-H2S mixture - no gas kij
    # checked values - accurate to with a gas constant for a standard PR EOS
    # These are very very good values confirming fugacity and fugacity coefficients are correct!
    ks = [[0,.0],[0.0,0]]
    eos = PRMIX(T=190.0, P=40.53e5, Tcs=[190.63, 373.55], Pcs=[46.17E5, 90.07E5], omegas=[0.01, 0.1], zs=[0.5, 0.5], kijs=ks)
    assert_allclose(eos.phis_l, [1.227364, 0.0114921], rtol=4e-4)
    assert_allclose(eos.fugacities_l, [2487250, 23288.73], rtol=3e-4)

    # CH4-H2S mixture - with kij - two phase, vapor frac 0.44424170
    # TODO use this as a test case
    # checked values - accurate to with a gas constant for a standard PR EOS
    ks = [[0,.083],[0.083,0]]
    xs = [0.1164203, 0.8835797]
    ys = [0.9798684, 0.0201315]

    eos = PRMIX(T=190.0, P=40.53e5, Tcs=[190.63, 373.55], Pcs=[46.17E5, 90.07E5], omegas=[0.01, 0.1], zs=xs, kijs=ks)
    assert_allclose([5.767042, 0.00774973], eos.phis_l, rtol=4e-4)
    assert_allclose([2721190, 27752.94], eos.fugacities_l, rtol=4e-4)
    eos = PRMIX(T=190.0, P=40.53e5, Tcs=[190.63, 373.55], Pcs=[46.17E5, 90.07E5], omegas=[0.01, 0.1], zs=ys, kijs=ks)
    assert_allclose([0.685195, 0.3401376], eos.phis_g, rtol=4e-4)
    assert_allclose([2721190, 27752.94], eos.fugacities_g, rtol=4e-4)
    
    # Check the kij can get copied
    kijs = [[0,.083],[0.083,0]]
    eos = PRMIX(T=190.0, P=40.53e5, Tcs=[190.6, 373.2], Pcs=[46e5, 89.4e5], omegas=[0.011, .097], zs=[.5, .5], kijs=kijs)
    eos2 = eos.to_TP_zs(T=200, P=5e6, zs=eos.zs)
    assert_allclose(eos2.kijs, kijs)
    assert_allclose(eos.T, 190)
    assert_allclose(eos.P, 40.53e5)
    assert_allclose(eos2.T, 200)
    assert_allclose(eos2.P, 5e6)
    assert eos.V_l != eos2.V_l
    
    
    # Test high temperature fugacities
    # Phase Identification Parameter would make both these roots the same phase
    eos = PRMIX(T=700, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    
    # The below depended on x0 being limited to real values even if negative
    # It is believed 2019-01-14 that this is not possible - the phase cannot
    # exist! So this should not be a problem.
#    fugacities_l_expect = [55126630.003539115, 27887160.323921766]
#    assert_allclose(eos.fugacities_l, fugacities_l_expect)
    
#    501788.3872471328, 500897.7585812287
    
    fugacities_g_expect = [501802.41653963586, 500896.73250179]
    assert_allclose(eos.fugacities_g, fugacities_g_expect)


def test_many_components():
    liquid_IDs = ['nitrogen', 'carbon dioxide', 'H2S', 'methane', 'ethane', 'propane', 'isobutane', 'butane', 'isopentane', 'pentane', 'Hexane', 'Heptane', 'Octane', 'Nonane', 'Decane', 'Undecane', 'Dodecane', 'Tridecane', 'Tetradecane', 'Pentadecane', 'Hexadecane', 'Heptadecane', 'Octadecane', 'Nonadecane', 'Eicosane', 'Heneicosane', 'Docosane', 'Tricosane', 'Tetracosane', 'Pentacosane', 'Hexacosane', 'Heptacosane', 'Octacosane', 'Nonacosane', 'Triacontane', 'Benzene', 'Toluene', 'Ethylbenzene', 'Xylene', '1,2,4-Trimethylbenzene', 'Cyclopentane', 'Methylcyclopentane', 'Cyclohexane', 'Methylcyclohexane']
    zs = [9.11975115499676e-05, 9.986813065240533e-05, 0.0010137795304828892, 0.019875879000370657, 0.013528874875432457, 0.021392773691700402, 0.00845450438914824, 0.02500218071904368, 0.016114189201071587, 0.027825798446635016, 0.05583179467176313, 0.0703116540769539, 0.07830577180555454, 0.07236459223729574, 0.0774523322851419, 0.057755091407705975, 0.04030134965162674, 0.03967043780553758, 0.03514481759005302, 0.03175471055284055, 0.025411123554079325, 0.029291866298718154, 0.012084986551713202, 0.01641114551124426, 0.01572454598093482, 0.012145363820829673, 0.01103585282423499, 0.010654818322680342, 0.008777712911254239, 0.008732073853067238, 0.007445155260036595, 0.006402875549212365, 0.0052908087849774296, 0.0048199150683177075, 0.015943943854195963, 0.004452253754752775, 0.01711981267072777, 0.0024032720444511282, 0.032178399403544646, 0.0018219517069058137, 0.003403378548794345, 0.01127516775495176, 0.015133143423489698, 0.029483213283483682]
    Tcs = [126.2, 304.2, 373.2, 190.56400000000002, 305.32, 369.83, 407.8, 425.12, 460.4, 469.7, 507.6, 540.2, 568.7, 594.6, 611.7, 639.0, 658.0, 675.0, 693.0, 708.0, 723.0, 736.0, 747.0, 755.0, 768.0, 778.0, 786.0, 790.0, 800.0, 812.0, 816.0, 826.0, 824.0, 838.0, 843.0, 562.05, 591.75, 617.15, 630.3, 649.1, 511.7, 553.8, 532.7, 572.1]
    Pcs = [3394387.5, 7376460.0, 8936865.0, 4599000.0, 4872000.0, 4248000.0, 3640000.0, 3796000.0, 3380000.0, 3370000.0, 3025000.0, 2740000.0, 2490000.0, 2290000.0, 2110000.0, 1980000.0, 1820000.0, 1680000.0, 1570000.0, 1480000.0, 1400000.0, 1340000.0, 1290000.0, 1160000.0, 1070000.0, 1030000.0, 980000.0, 920000.0, 870000.0, 950000.0, 800000.0, 883000.0, 800000.0, 826000.0, 600000.0, 4895000.0, 4108000.0, 3609000.0, 3732000.0, 3232000.0, 4510000.0, 4080000.0, 3790000.0, 3480000.0]
    omegas = [0.04, 0.2252, 0.1, 0.008, 0.098, 0.152, 0.17600000000000002, 0.193, 0.22699999999999998, 0.251, 0.2975, 0.3457, 0.39399999999999996, 0.444, 0.49, 0.535, 0.562, 0.623, 0.679, 0.6897, 0.742, 0.7564, 0.8087, 0.8486, 0.8805, 0.9049, 0.9423, 1.0247, 1.0411, 1.105, 1.117, 1.214, 1.195, 1.265, 1.26, 0.212, 0.257, 0.301, 0.3118, 0.3771, 0.1921, 0.239, 0.213, 0.2477]
    eos = PRMIX(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
    
    
    assert_allclose(eos.V_g, 0.019092551264336028)
    assert_allclose(eos.V_l, 0.0002453974598582871)

    assert_allclose(eos.a_alpha, 11.996512274167202)
    assert_allclose(eos.da_alpha_dT, -0.0228875173310534)
    assert_allclose(eos.d2a_alpha_dT2, 5.997880989552689e-05)
    
    V_over_F, xs, ys, eos_l, eos_g = eos.sequential_substitution_VL()
    assert_allclose(V_over_F, 0.03547152723457448, rtol=5e-5)
    assert_allclose(xs, [5.729733527056475e-06, 4.0516737456029636e-05, 0.0006069285358060455, 0.0030221509527402807, 0.006670434145198826, 0.016845301723389206, 0.007760188627667261, 0.023716884273864994, 0.016120427201854567, 0.028071761635467454, 0.05738553540904704, 0.07269474153625576, 0.08111242740513086, 0.07500425089850274, 0.08029153901604559, 0.05987718593915933, 0.04178296619077928, 0.04112921011785296, 0.036437266797871466, 0.03292250673929231, 0.02634563984465752, 0.03036910265441899, 0.01252942406087858, 0.017014682097712515, 0.01630283227693387, 0.012592022051117679, 0.011441707659942228, 0.011046660229078003, 0.009100522335947752, 0.009053204855420115, 0.007718958506744987, 0.006638347887060363, 0.005485383723073785, 0.004997172405387115, 0.016530298798161255, 0.004574527233511734, 0.017701045589161052, 0.0024893880550883388, 0.033338891413257424, 0.0018885749821301962, 0.003452886350289371, 0.011614131308001385, 0.01553751739014118, 0.030473502992154296],
                    rtol=5e-5, atol=1e-5)
    assert_allclose(ys, [0.0024152052956508234, 0.0017137289677579672, 0.01207671927772537, 0.47815613478650093, 0.2000210244617312, 0.14504592692452017, 0.02733407832487352, 0.05995147988851196, 0.01594456782197141, 0.02113765961031682, 0.013583058932377816, 0.005511633136594507, 0.0019882447609517653, 0.0005879833453478944, 0.0002496870786300975, 5.189233339016621e-05, 1.3788073507311385e-05, 4.047880869664237e-06, 1.0231799554219332e-06, 4.3437603783102945e-07, 1.0686553748606369e-07, 5.9095141645558586e-08, 8.391056490347942e-09, 4.875695250293468e-09, 1.7792547398641979e-09, 6.437996463823593e-10, 2.5830362538596066e-10, 7.806691559916385e-11, 3.36860845201539e-11, 6.662408195909387e-12, 5.247905701692434e-12, 5.760475376250616e-13, 8.102134731211449e-13, 1.1667142269975863e-13, 1.390262805287062e-12, 0.0011274391521227964, 0.0013151450162989817, 6.163776207935758e-05, 0.0006227356628028977, 1.035657941516073e-05, 0.0020571809675571477, 0.002058197874178186, 0.004137558093848116, 0.0025556267157302547],
                    rtol=5e-5, atol=1e-5)
    
    V_over_F, xs, ys, eos_l, eos_g = PRMIX(T=669.1, P=3.25e6, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas).sequential_substitution_VL()
    assert_allclose(V_over_F, 0.341342933080815, rtol=1e-4)

    V_over_F, xs, ys, eos_l, eos_g = PRMIX(T=669.1, P=3.19e6, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas).sequential_substitution_VL()
    assert_allclose(V_over_F, 0.40427364770048313, rtol=1e-4)

    V_over_F, xs, ys, eos_l, eos_g = PRMIX(T=660, P=3.2e6, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas).sequential_substitution_VL()
    assert_allclose(V_over_F, 0.27748085589254096, rtol=1e-4)
    
    assert_allclose(eos.mechanical_critical_point(), 
                    (622.597863984166, 1826304.23759842))
    
    
    # Make it even slower
    zs = [i*0.25 for i in zs]
    zs = zs + zs + zs + zs
    Tcs = Tcs + Tcs + Tcs + Tcs
    Pcs = Pcs + Pcs + Pcs + Pcs
    omegas = omegas + omegas + omegas + omegas
    eos = PRMIX(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)


def test_derivatives_density():
    # Check some extra derivatives
    T = 420.0
    zs = [.5, .5]
    P = 2.7e6
    Tcs = [305.32, 540.2]
    Pcs = [4872000.0, 2740000.0]
    omegas = [0.098, 0.3457]
    kijs=[[0,0.0067],[0.0067,0]]
    
    eos = PRMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    assert_allclose(eos.dP_drho_g, 77.71290396836963)
    assert_allclose(eos.dP_drho_l, 1712.0682171304466)

@pytest.mark.xfail
def test_density_extrapolation():
    # no longer used - different cubic formulation, plus extrapolation is not being used
    # Check some extra derivatives
    T = 420.0
    zs = [.5, .5]
    P = 2.7e6
    Tcs = [305.32, 540.2]
    Pcs = [4872000.0, 2740000.0]
    omegas = [0.098, 0.3457]
    kijs=[[0,0.0067],[0.0067,0]]
    eos = PRMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    # Check the discriminant is zero
    P_transition = newton(eos.discriminant_at_T_zs, 2.7E6, tol=1e-12)
    assert_allclose(P_transition, 2703430.0056912485)
    
    P = P_transition + .01
    eos = PRMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    assert eos.raw_volumes[0].imag == 0
    # Check there is a small imaginary component in the others
    assert all(abs(eos.raw_volumes[i].imag) > 1e-9 for i in (1, 2))
    
    P = P_transition - .01
    eos = PRMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    # Check the imaginary components are infinitesimally all small (real roots)
    assert all(abs(eos.raw_volumes[i].imag) < 1e-15 for i in (0, 1, 2))
    
    # See the second pressure transition place
    P_transition = newton(eos.discriminant_at_T_zs, 1e10, tol=1e-12)
    assert_allclose(P_transition, 110574232.59024328)
    
    # Below the transition point = one real root in this case.    
    P = P_transition - .01
    eos = PRMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    # Third root is the important one in this case
    assert abs(eos.raw_volumes[2].imag) < 1e-15
    # Check there is a small but larger imaginary component in the others
    assert all(abs(eos.raw_volumes[i].imag) > 1e-9 for i in (0, 1))
    
    
    P = P_transition + 1
    eos = PRMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    # Third root is the important one in this case
    assert abs(eos.raw_volumes[2].imag) < 1e-15
    # Check there is a very tiny imaginary component in the others
    assert all(abs(eos.raw_volumes[i].imag) < 1e-15 for i in (0, 1))
    
    
    eos = PRMIX(T=T, P=2.8E6, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    assert_allclose(eos.V_g_extrapolated(), 0.0005133249130364282)



def test_mechanical_critical_point():
    '''Test from:
    Watson, Harry A. J., and Paul I. Barton. "Reliable Flash Calculations: 
    Part 3. A Nonsmooth Approach to Density Extrapolation and Pseudoproperty
    Evaluation." Industrial & Engineering Chemistry Research, November 11, 2017.
    '''
    Tcs = [305.32, 540.2]
    Pcs = [4872000.0, 2740000.0]
    omegas = [0.098, 0.3457]
    zs = [.5, .5]

    eos = PRMIX(T=300, P=1e5, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=[[0,0.0067],[0.0067,0]])
    eos = eos.to_mechanical_critical_point()
    assert_allclose(eos.T, 439.18798438998385, rtol=1e-5)
    assert_allclose(eos.P, 3380688.869519021, rtol=1e-5)
    assert_allclose(1/eos.V_l, 3010, rtol=1e-3) # A more correct answer
    assert_allclose(eos.rho_l, 3012.174720884504, rtol=1e-6)
    
    # exact answer believed to be:
#    3011.7228497511787 # mol/m^3
    # 439.18798489 with Tc = 439.18798489 or so.
    
def test_sequential_substitution_VL():
    omegas = [0.2252, 0.2975]
    Tcs = [304.2, 507.4]
    Pcs = [7.38E6, 3.014E6]
    kijs=[[0,0],[0,0]]
    
    eos = PRMIX(T=313.0, P=1E6, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=[.5, .5], kijs=kijs)
    V_over_F, xs, ys, eos_l, eos_g = eos.sequential_substitution_VL()
    assert_allclose(V_over_F, 0.4128783868475084)
    assert_allclose(xs, [0.17818473607425783, 0.8218152639257423])
    assert_allclose(ys, [0.9576279672468324, 0.04237203275316752])    
    
    
def test_TPD():
    # Two-phase nitrogen-methane
    eos = PRMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    eos_trial = PRMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    # Get a negative TPD proving there is a phase split
    TPD = eos.TPD(eos.T, eos.zs, eos.lnphis_g, eos_trial.zs, eos_trial.lnphis_l)
    assert_allclose(TPD, -471.3629956139435)
    
    



all_zs_SRKMIX_CH4_H2S = [[0.9885, 0.0115], [0.9813, 0.0187], [0.93, 0.07], 
      [.5, .5], [0.112, 0.888], [.11, .89]]
all_expected_SRKMIX_CH4_H2S = [[.9885],
            [0.9813, 0.10653187, 0.52105697, 0.92314194],
           [.93, 0.11616261, 0.48903294, 0.98217018],
            [0.5, 0.11339494, 0.92685263, 0.98162794],
            [0.112, 0.50689794, 0.9243395, 0.98114659],
            [.11, 0.51373521, 0.92278719, 0.9809485]
           ]

@pytest.mark.xfail
def test_Stateva_Tsvetkov_TPDF_SRKMIX_CH4_H2S():
    # ALL WRONG - did not use two EOS correctly, did not use SHGO
    '''Data and examples from 
    Ivanov, Boyan B., Anatolii A. Galushko, and Roumiana P. Stateva. "Phase 
    Stability Analysis with Equations of State-A Fresh Look from a Different 
    Perspective." Industrial & Engineering Chemistry Research 52, no. 32 
    (August 14, 2013): 11208-23. https://doi.org/10.1021/ie401072x.
    
    Some of the points are a little off - explained by differences in the
    a, b values of the SRK c1, and c2 values, as well as the gas constant; this
    is a very sensitive calculation. However, all the trivial points match
    exactly, and no *extra* roots could be found at all.

    Note: future scipy.minimize behavior might make some guesses converge elsewhere.
    
    This example is the closest - other examples do not match so well, though
    there is no reason for that! Perhaps this is the "easiest" case.
    
    '''
    all_guesses = [[[0.98]], # No other answers close to zero found
           [[0.98], [.11], [.5, .6], [0.9, 0.91]],
           [[.92], [.12], [0.5], [0.98]],
           [[.47, .49, .499], [.11], [.92], [0.98]],
           [[0.11], [.505, .52], [0.9], [0.98]],
           [[.12], [0.5], [0.9], [0.98]]
          ]

    for i in range(len(all_zs_SRKMIX_CH4_H2S)):
        zs = all_zs_SRKMIX_CH4_H2S[i]
        kijs = [[0,.08],[0.08,0]]
        eos = SRKMIX(T=190.0, P=40.53e5, Tcs=[190.6, 373.2], Pcs=[46e5, 89.4e5],
                     omegas=[0.008, .1], zs=zs, kijs=kijs)
        Z_eos, prefer, alt = eos_Z_test_phase_stability(eos)
        
        def func(z1):
            zs_trial = [z1, 1-z1]
            eos2 = eos.to_TP_zs(T=eos.T, P=eos.P, zs=zs_trial)
            
            Z_trial = eos_Z_trial_phase_stability(eos2, prefer, alt)    
            TPD = eos.Stateva_Tsvetkov_TPDF_broken(Z_eos, Z_trial, eos.zs, zs_trial)
            return TPD
        guesses = all_guesses[i]
        expected = all_expected_SRKMIX_CH4_H2S[i]
        for j in range(len(expected)):
            for k in range(len(guesses[j])):
                ans = minimize(func, guesses[j][k], bounds=[(1e-9, 1-1e-6)])
                assert_allclose(float(ans['x']), expected[j], rtol=1e-6)        

@pytest.mark.xfail
def test_d_TPD_Michelson_modified_SRKMIX_CH4_H2S():
    # ALL WRONG - did not use two EOS correctly, did not use SHGO
    all_guesses = [[[0.98]],
               [[0.98], [[6530, 18900]], [[59000, 53600]], [0.91]],
               [[.92], [[9, 18]], [[20, 4]], [0.98]],
               [[.499], [[6., 18.]], [.92], [0.98]],
               [[0.11], [[142, 140]], [[6, 19]], [0.98]],
               [[.12], [[141, 141]], [[39, 9]], [0.98]]
              ]
    for i in range(len(all_zs_SRKMIX_CH4_H2S)):
        zs = all_zs_SRKMIX_CH4_H2S[i]
        kijs = [[0,.08],[0.08,0]]
        eos = SRKMIX(T=190.0, P=40.53e5, Tcs=[190.6, 373.2], Pcs=[46e5, 89.4e5], omegas=[0.008, .1], zs=zs, kijs=kijs)
        Z_eos, prefer, alt = eos_Z_test_phase_stability(eos)
    
        def func(alphas):
            Ys = [(alph/2.)**2 for alph in alphas]
            ys = normalize(Ys)
            eos2 = eos.to_TP_zs(T=eos.T, P=eos.P, zs=ys)
            Z_trial = eos_Z_trial_phase_stability(eos2, prefer, alt)    
            TPD = eos.d_TPD_Michelson_modified(Z_eos, Z_trial, eos.zs, alphas)
            return TPD
    
        guesses = all_guesses[i]
        expected = all_expected_SRKMIX_CH4_H2S[i]
        for j in range(len(expected)):
            for k in range(len(guesses[j])):
                if type(guesses[j][k])== list:
                    guess = guesses[j][k]
                else:
                    x0 = guesses[j][k]
                    x1 = 1 - x0
                    guess = [xi**0.5*2 for xi in [x0, x1]] # convert to appropriate basis
                
                # Initial guesses were obtained by trying repetitively and are specific to NM
                ans = minimize(func, guess, tol=1e-12, method='Nelder-Mead') 
                Ys = [(alph/2.)**2 for alph in ans['x']]
                ys = normalize(Ys)
                assert ans['fun'] < 1e-12
                assert_allclose(ys[0], expected[j], rtol=1e-7)        


@pytest.mark.xfail
def test_Stateva_Tsvetkov_TPDF_PRMIX_Nitrogen_Methane_Ethane():
    # ALL WRONG - did not use two EOS correctly, did not use SHGO
    '''Data and examples from 
    Ivanov, Boyan B., Anatolii A. Galushko, and Roumiana P. Stateva. "Phase 
    Stability Analysis with Equations of State-A Fresh Look from a Different 
    Perspective." Industrial & Engineering Chemistry Research 52, no. 32 
    (August 14, 2013): 11208-23. https://doi.org/10.1021/ie401072x.
    
    Some of the points are a little off - explained by differences in the
    a, b values of the SRK c1, and c2 values, as well as the gas constant; this
    is a very sensitive calculation. However, all the trivial points match
    exactly. One extra root was found for the third case.
    
    Note: future scipy.minimize behavior might make some guesses converge elsewhere.
    '''
    # Problem 5: Nitrogen + Methane + Ethane at T = 270 K and P = 76 bar.
    # PR
    # Sources 8,9,11,14,17,20,43,45,46
    T = 270.0
    P = 76E5
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    all_zs = [[0.3, 0.1, 0.6],
            [.15, .3, .55],
            [.08, .38, .54],
            [.05, .05, .9]]
    
#    0.13303524, 0.06779703,; 0.31165468, 0.1016158 
    
    all_expected = [[[0.35201577,  0.10728462], [0.3, 0.1], [0.08199763,  0.04915481]],
                    [ [0.06451677,  0.19372499], [0.17128871, 0.31864581], [0.15, 0.3] ],
                    [[0.08,  0.38], [0.09340211,  0.40823117]],
                    [[0.05, 0.05]]
                   ]
    
    all_guesses = [[[[.35, 0.107]], [[.29,  0.107]], [[.08,  0.05]]],
              [[[.08,  0.05]], [ [.2,  0.3]], [[.155,  0.31]]],
               [[[.09,  0.39]], [[.2,  0.4]]],
               [[[.01,  0.03]]]
              ]
    
    for i in range(len(all_zs)):
        zs = all_zs[i]
        eos = PRMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, kijs=kijs, zs=zs)
        Z_eos, prefer, alt = eos_Z_test_phase_stability(eos)
    
        def func(zs):
            zs_trial = [float(zs[0]), float(zs[1]), float(1 - sum(zs))]
            eos2 = eos.to_TP_zs(T=eos.T, P=eos.P, zs=zs_trial)
            Z_trial = eos_Z_trial_phase_stability(eos2, prefer, alt)
            TPD = eos.Stateva_Tsvetkov_TPDF_broken(Z_eos, Z_trial, eos.zs, zs_trial)
            return TPD
    
        guesses = all_guesses[i]
        expected = all_expected[i]
        for j in range(len(expected)):
            for k in range(len(guesses[j])):
                ans = minimize(func, guesses[j][k], bounds=[(1e-9, .5-1e-6), (1e-9, .5-1e-6)], tol=1e-11)
                assert_allclose(ans['x'], expected[j], rtol=5e-6)        

    
def test_PRMIX_VS_PR():
    # Test solution for molar volumes
    eos = PRMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., P=1E6)
    Vs_fast = eos.volume_solutions(299, 1E6, eos.b, eos.delta, eos.epsilon, eos.a_alpha)
    Vs_slow = eos.volume_solutions(299, 1E6, eos.b, eos.delta, eos.epsilon, eos.a_alpha, quick=False)
    Vs_expected = [(0.00013022212513965833+0j), (0.001123631313468268+0.0012926967234386066j), (0.001123631313468268-0.0012926967234386066j)]
    assert_allclose(Vs_fast, Vs_expected)
    assert_allclose(Vs_slow, Vs_expected)
    
    # Test of a_alphas
    a_alphas = (3.8012620034344384, -0.006647930535193548, 1.693013909536469e-05)
    a_alphas_fast = eos.a_alpha_and_derivatives(299, quick=True)
    assert_allclose(a_alphas, a_alphas_fast)
    a_alphas_slow = eos.a_alpha_and_derivatives(299, quick=False)
    assert_allclose(a_alphas, a_alphas_slow)
    
    # PR back calculation for T
    eos = PRMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], V=0.00013022212513965833, P=1E6)
    assert_allclose(eos.T, 299)
    T_slow = eos.solve_T(P=1E6, V=0.00013022212513965833, quick=False)
    assert_allclose(T_slow, 299)
    
    
    diffs_1 = [582232.4757941177, -3665179372374.2607, 1.5885511093470827e-07, -2.728379428132085e-13, 6295044.547927793, 1.717527004374123e-06]
    diffs_2 = [-506.20125231401545, 4.482162818098147e+17, 1.1688517647207335e-09, 9.103364399605293e-21, -291578743623.699, 2.56468444397071e-15]
    diffs_mixed = [-3.772509038556631e-15, -20523296734.825638, 0.0699416812561707]
    departures = [-31134.75084346042, -72.47561931957617, 25.165386034971867]
    known_derivs_deps = [diffs_1, diffs_2, diffs_mixed, departures]
    
    for f in [True, False]:
        main_calcs = eos.derivatives_and_departures(eos.T, eos.P, eos.V_l, eos.b, eos.delta, eos.epsilon, eos.a_alpha, eos.da_alpha_dT, eos.d2a_alpha_dT2, quick=f)
        main_calcs = (main_calcs[0:6], main_calcs[6:12], main_calcs[12:15], main_calcs[15:])
        for i, j in zip(known_derivs_deps, main_calcs):
            assert_allclose(i, j)
        
    # Integration tests
    eos = PRMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], V=0.00013, T=299)
    fast_vars = vars(eos)
    eos.set_properties_from_solution(eos.T, eos.P, eos.V, eos.b, eos.delta, eos.epsilon, eos.a_alpha, eos.da_alpha_dT, eos.d2a_alpha_dT2, quick=False)
    slow_vars = vars(eos)
    [assert_allclose(slow_vars[i], j) for (i, j) in fast_vars.items() if isinstance(j, float)]


def test_PR78MIX():
    # Copied and pasted example from PR78.
    eos = PR78MIX(Tcs=[632], Pcs=[5350000], omegas=[0.734], zs=[1], T=299., P=1E6)
    three_props = [eos.V_l, eos.H_dep_l, eos.S_dep_l]
    expect_props = [8.35196289693885e-05, -63764.67109328409, -130.7371532254518]
    assert_allclose(three_props, expect_props)

    # Fugacities
    eos = PR78MIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.6, 0.7], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    # Numerically test fugacities at one point, with artificially high omegas
    def numerical_fugacity_coefficient(n1, n2=0.5, switch=False, l=True):
        if switch:
            n1, n2 = n2, n1
        tot = n1+n2
        zs = [i/tot for i in [n1,n2]]
        a = PR78MIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.6, 0.7], zs=zs, kijs=[[0,0],[0,0]])
        phi = a.phi_l if l else a.phi_g
        return tot*log(phi)

    phis = [[derivative(numerical_fugacity_coefficient, 0.5, dx=1E-6, order=25, args=(0.5, i, j)) for i in [False, True]] for j in [False, True]]
    assert_allclose(phis, [eos.lnphis_g, eos.lnphis_l])


def test_SRKMIX_quick():
    # Two-phase nitrogen-methane
    eos = SRKMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    Vs_expected = [4.104756961475809e-05, 0.0002040998264950349, 0.0007110158049778294]
    assert_allclose(eos.sorted_volumes, Vs_expected)

    # Test of a_alphas
    a_alphas = (0.21053508135768303, -0.0007568164048417844, 4.650780763765838e-06)
    a_alphas_fast = eos.a_alpha_and_derivatives(115)
    assert_allclose(a_alphas, a_alphas_fast)
    a_alphas_slow = eos.a_alpha_and_derivatives(115, quick=False)
    assert_allclose(a_alphas, a_alphas_slow)
    assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False), rtol=1e-12)

    # back calculation for T, both solutions
    for V in [4.104756961475803e-05, 0.0007110158049778292]:
        eos = SRKMIX(V=V, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
        assert_allclose(eos.T, 115)
        T_slow = eos.solve_T(P=1E6, V=V, quick=False)
        assert_allclose(T_slow, 115)


    # Fugacities
    eos = SRKMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(eos.phis_l, [1.6356832861093693, 0.14476563850405255])
    assert_allclose(eos.phis_g, [0.8842742560249208, 0.7236415842381881])
    
    # Numerically test fugacities at one point
    def numerical_fugacity_coefficient(n1, n2=0.5, switch=False, l=True):
        if switch:
            n1, n2 = n2, n1
        tot = n1+n2
        zs = [i/tot for i in [n1,n2]]
        a = SRKMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=zs, kijs=[[0,0],[0,0]])
        phi = a.phi_l if l else a.phi_g
        return tot*log(phi)

    phis = [[derivative(numerical_fugacity_coefficient, 0.5, dx=1E-6, order=25, args=(0.5, i, j)) for i in [False, True]] for j in [False, True]]
    assert_allclose(phis, [eos.lnphis_g, eos.lnphis_l])

    # Gas phase only test point
    a = SRKMIX(T=300, P=1E7, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(a.phis_g, [1.0200087028463556, 0.8717783536379076]) 


def test_SRKMIX_vs_SRK():
    # Copy and paste from SRK, changed to list inputs only
    # Test solution for molar volumes
    eos = SRKMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., P=1E6)
    Vs_fast = eos.volume_solutions(299, 1E6, eos.b, eos.delta, eos.epsilon, eos.a_alpha)
    Vs_slow = eos.volume_solutions(299, 1E6, eos.b, eos.delta, eos.epsilon, eos.a_alpha, quick=False)
    Vs_expected = [(0.0001468210773547259+0j), (0.0011696016227365465+0.001304089515440735j), (0.0011696016227365465-0.001304089515440735j)]
    assert_allclose(Vs_fast, Vs_expected)
    assert_allclose(Vs_slow, Vs_expected)
    
    # Test of a_alphas
    a_alphas = (3.72718144448615, -0.007332994130304653, 1.9476133436500582e-05)
    a_alphas_fast = eos.a_alpha_and_derivatives(299)
    assert_allclose(a_alphas, a_alphas_fast)
    assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False), rtol=1e-12)
    assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False, quick=False), rtol=1e-12)

    # PR back calculation for T
    eos = SRKMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], V=0.0001468210773547259, P=1E6)
    assert_allclose(eos.T, 299)
    T_slow = eos.solve_T(P=1E6, V=0.0001468210773547259, quick=False)
    assert_allclose(T_slow, 299)
    
    # Derivatives
    diffs_1, diffs_2, diffs_mixed, departures = ([507071.3781579619, -2693848855910.751, 1.8823304694521492e-07, -3.712160753955569e-13, 5312563.421932224, 1.97210894377967e-06],
                                                 [-495.5254299681785, 2.6851518388403037e+17, 1.3462644444996599e-09, 1.3735648667748027e-20, -201856509533.58496, 3.800656805086307e-15],
                                                 [-4.9913489930067516e-15, -14322101736.003756, 0.06594010907198579],
                                                 [-31754.663859649736, -74.37327204447028, 28.936530624645137])
    known_derivs_deps = [diffs_1, diffs_2, diffs_mixed, departures]
    
    for f in [True, False]:
        main_calcs = eos.derivatives_and_departures(eos.T, eos.P, eos.V_l, eos.b, eos.delta, eos.epsilon, eos.a_alpha, eos.da_alpha_dT, eos.d2a_alpha_dT2, quick=f)
        main_calcs = (main_calcs[0:6], main_calcs[6:12], main_calcs[12:15], main_calcs[15:])
        for i, j in zip(known_derivs_deps, main_calcs):
            assert_allclose(i, j)
    
        
    # Integration tests
    eos = SRKMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299.,V=0.00013)
    fast_vars = vars(eos)
    eos.set_properties_from_solution(eos.T, eos.P, eos.V, eos.b, eos.delta, eos.epsilon, eos.a_alpha, eos.da_alpha_dT, eos.d2a_alpha_dT2, quick=False)
    slow_vars = vars(eos)
    [assert_allclose(slow_vars[i], j) for (i, j) in fast_vars.items() if isinstance(j, float)]



def test_VDWMIX_vs_VDW():
    eos = VDWMIX(Tcs=[507.6], Pcs=[3025000], zs=[1], T=299., P=1E6)
    three_props = [eos.V_l, eos.H_dep_l, eos.S_dep_l]
    expect_props = [0.00022332985608164609, -13385.727374687076, -32.65923125080434]
    assert_allclose(three_props, expect_props)
    
    # Test of a_alphas
    a_alphas = [2.4841053385218554, 0, 0]
    a_alphas_fast = eos.a_alpha_and_derivatives(299)
    assert_allclose(a_alphas, a_alphas_fast)
    [assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False, quick=i), rtol=1e-12) for i in (True, False)]

    # Back calculation for P
    eos = VDWMIX(Tcs=[507.6], Pcs=[3025000], zs=[1], T=299, V=0.00022332985608164609)
    assert_allclose(eos.P, 1E6)
    
    # Back calculation for T
    eos = VDWMIX(Tcs=[507.6], Pcs=[3025000], zs=[1], P=1E6, V=0.00022332985608164609)
    assert_allclose(eos.T, 299)


def test_VDWIX_quick():
    # Two-phase nitrogen-methane
    eos = VDWMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    Vs_expected = [5.881369844882986e-05, 0.00016108242301576212, 0.0007770872375800778]
    assert_allclose(eos.sorted_volumes, Vs_expected)

    # Test of a_alphas
    a_alphas = [0.18035232263614895, 0.0, 0.0]
    a_alphas_fast = eos.a_alpha_and_derivatives(115)
    assert_allclose(a_alphas, a_alphas_fast)
    a_alphas_slow = eos.a_alpha_and_derivatives(115, quick=False)
    assert_allclose(a_alphas, a_alphas_slow)

    # back calculation for T, both solutions
    for V in [5.881369844882989e-05, 0.0007770872375800777]:
        eos = VDWMIX(V=V, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
        assert_allclose(eos.T, 115)
        T_slow = eos.solve_T(P=1E6, V=V, quick=False)
        assert_allclose(T_slow, 115)


    # Fugacities
    eos = VDWMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(eos.phis_l, [1.7090665338410205, 0.414253699455241])
    assert_allclose(eos.phis_g, [0.896941472676147, 0.7956530879998579])
    
    # Numerically test fugacities at one point
    def numerical_fugacity_coefficient(n1, n2=0.5, switch=False, l=True):
        if switch:
            n1, n2 = n2, n1
        tot = n1+n2
        zs = [i/tot for i in [n1,n2]]
        a = VDWMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], zs=zs, kijs=[[0,0],[0,0]])
        phi = a.phi_l if l else a.phi_g
        return tot*log(phi)

    phis = [[derivative(numerical_fugacity_coefficient, 0.5, dx=1E-6, order=25, args=(0.5, i, j)) for i in [False, True]] for j in [False, True]]
    assert_allclose(phis, [eos.lnphis_g, eos.lnphis_l])

    # Gas phase only test point
    a = VDWMIX(T=300, P=1E7, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(a.phis_g, [0.9564004482475513, 0.8290411371501448]) 


def test_PRSVMIX_vs_PRSV():
    eos = PRSVMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., P=1E6, kappa1s=[0.05104])
    three_props = [eos.V_l, eos.H_dep_l, eos.S_dep_l]
    expect_props = [0.0001301269135543934, -31698.926746698795, -74.16751538228138]
    assert_allclose(three_props, expect_props)
    
    # Test of a_alphas
    a_alphas = [3.812985698311453, -0.006976903474851659, 2.0026560811043733e-05]
    
    [assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False, quick=i), rtol=1e-12) for i in (True, False)]
    
    a_alphas_fast = eos.a_alpha_and_derivatives(299)
    assert_allclose(a_alphas, a_alphas_fast, rtol=1e-12)
    
    a_alphas_fast = eos.a_alpha_and_derivatives(299, quick=False)
    assert_allclose(a_alphas, a_alphas_fast, rtol=1e-12)
    
    # PR back calculation for T
    eos = PRSVMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], V=0.0001301269135543934, P=1E6, kappa1s=[0.05104])
    assert_allclose(eos.T, 299)
    T_slow = eos.solve_T(P=1E6, V=0.0001301269135543934, quick=False)
    assert_allclose(T_slow, 299)
    
    
    # Test the bool to control its behavior
    eos = PRSVMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=406.08, P=1E6, kappa1s=[0.05104])
    assert_allclose(eos.kappas, 0.7977689278061457)
    eos.kappa1_Tr_limit = True
    eos.__init__(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=406.08, P=1E6, kappa1s=[0.05104])
    assert_allclose(eos.kappas, 0.8074380841890093)
    
    # Test the limit is not enforced while under Tr =0.7
    eos = PRSVMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=304.56, P=1E6, kappa1s=[0.05104])
    assert_allclose(eos.kappas, 0.8164956255888178)
    eos.kappa1_Tr_limit = True
    eos.__init__(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=304.56, P=1E6, kappa1s=[0.05104])
    assert_allclose(eos.kappas, 0.8164956255888178)


def test_PRSVMIX_quick():
    # Two-phase nitrogen-methane
    eos = PRSVMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    Vs_expected = [3.6235536165643867e-05, 0.00019428009417235906, 0.0007002423865480607]
    assert_allclose(eos.sorted_volumes, Vs_expected)

    # Test of a_alphas
    a_alphas = (0.21897593315687267, -0.0006396071449056316, 3.715015383907643e-06)
    a_alphas_fast = eos.a_alpha_and_derivatives(115)
    assert_allclose(a_alphas, a_alphas_fast)
    a_alphas_slow = eos.a_alpha_and_derivatives(115, quick=False)
    assert_allclose(a_alphas, a_alphas_slow)
    [assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False, quick=i), rtol=1e-12) for i in (True, False)]

    # back calculation for T, both solutions
    for V in [3.623553616564366e-05, 0.0007002423865480607]:
        eos = PRSVMIX(V=V, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
        assert_allclose(eos.T, 115)
        T_slow = eos.solve_T(P=1E6, V=V, quick=False)
        assert_allclose(T_slow, 115)


    # Fugacities
    eos = PRSVMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(eos.phis_l, [1.5881151663681092, 0.14570244654356812])
    assert_allclose(eos.phis_g, [0.8731073123670093, 0.7157562213377993])
    
    # Numerically test fugacities at one point
    def numerical_fugacity_coefficient(n1, n2=0.5, switch=False, l=True):
        if switch:
            n1, n2 = n2, n1
        tot = n1+n2
        zs = [i/tot for i in [n1,n2]]
        a = PRSVMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=zs, kijs=[[0,0],[0,0]])
        phi = a.phi_l if l else a.phi_g
        return tot*log(phi)

    phis = [[derivative(numerical_fugacity_coefficient, 0.5, dx=1E-6, order=25, args=(0.5, i, j)) for i in [False, True]] for j in [False, True]]
    assert_allclose(phis, [eos.lnphis_g, eos.lnphis_l])

    # Gas phase only test point
    eos = PRSVMIX(T=300, P=1E7, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(eos.phis_g, [0.9859363207073754, 0.8344831291870667]) 


def test_PRSV2MIX_vs_PRSV():
    eos = PRSV2MIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., P=1E6, kappa1s=[0.05104], kappa2s=[0.8634], kappa3s=[0.460])
    three_props = [eos.V_l, eos.H_dep_l, eos.S_dep_l]
    expect_props = [0.00013018825759153257, -31496.184168729033, -73.6152829631142]
    assert_allclose(three_props, expect_props)
    
    # Test of PRSV2 a_alphas
    a_alphas = (3.80542021117275, -0.006873163375791913, 2.3078023705053794e-05)
    
    a_alphas_fast = eos.a_alpha_and_derivatives(299)
    assert_allclose(a_alphas, a_alphas_fast)
    a_alphas_fast = eos.a_alpha_and_derivatives(299, quick=False)
    assert_allclose(a_alphas, a_alphas_fast)
    
    [assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False, quick=i), rtol=1e-12) for i in (True, False)]

    # PSRV2 back calculation for T
    eos = PRSV2MIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], V=0.00013018825759153257, P=1E6, kappa1s=[0.05104], kappa2s=[0.8634], kappa3s=[0.460])
    assert_allclose(eos.T, 299)
    T_slow = eos.solve_T(P=1E6, V=0.00013018825759153257, quick=False)
    assert_allclose(T_slow, 299)

    # Check this is the same as PRSV
    eos = PRSVMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., P=1E6, kappa1s=[0.05104])
    three_props_PRSV = [eos.V_l, eos.H_dep_l, eos.S_dep_l]
    eos = PRSV2MIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., P=1E6, kappa1s=[0.05104])
    three_props_PRSV2 = [eos.V_l, eos.H_dep_l, eos.S_dep_l]
    assert_allclose(three_props_PRSV, three_props_PRSV2)
    

def test_PRSV2MIX_quick():
    # Two-phase nitrogen-methane
    eos = PRSV2MIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    Vs_expected = [3.6235536165643867e-05, 0.00019428009417235906, 0.0007002423865480607]
    assert_allclose(eos.sorted_volumes, Vs_expected)

    # Test of a_alphas
    a_alphas = (0.21897593315687267, -0.0006396071449056315, 3.715015383907642e-06)
    a_alphas_fast = eos.a_alpha_and_derivatives(115)
    assert_allclose(a_alphas, a_alphas_fast)
    a_alphas_slow = eos.a_alpha_and_derivatives(115, quick=False)
    assert_allclose(a_alphas, a_alphas_slow)
    
    [assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False, quick=i), rtol=1e-12) for i in (True, False)]

    # back calculation for T, both solutions
    for V in [3.623553616564366e-05, 0.0007002423865480607]:
        eos = PRSV2MIX(V=V, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
        assert_allclose(eos.T, 115)
        T_slow = eos.solve_T(P=1E6, V=V, quick=False)
        assert_allclose(T_slow, 115)


    # Fugacities
    eos = PRSV2MIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(eos.phis_l, [1.5881151663681092, 0.14570244654356812])
    assert_allclose(eos.phis_g, [0.8731073123670093, 0.7157562213377993])
    
    # Numerically test fugacities at one point
    def numerical_fugacity_coefficient(n1, n2=0.5, switch=False, l=True):
        if switch:
            n1, n2 = n2, n1
        tot = n1+n2
        zs = [i/tot for i in [n1,n2]]
        a = PRSVMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=zs, kijs=[[0,0],[0,0]])
        phi = a.phi_l if l else a.phi_g
        return tot*log(phi)

    phis = [[derivative(numerical_fugacity_coefficient, 0.5, dx=1E-6, order=25, args=(0.5, i, j)) for i in [False, True]] for j in [False, True]]
    assert_allclose(phis, [eos.lnphis_g, eos.lnphis_l])

    # Gas phase only test point
    eos = PRSV2MIX(T=300, P=1E7, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(eos.phis_g, [0.9859363207073754, 0.8344831291870667]) 


def test_TWUPRMIX_vs_TWUPR():
    # Copy and pasted
    # Test solution for molar volumes
    eos = TWUPRMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., P=1E6)
    Vs_fast = eos.volume_solutions(299, 1E6, eos.b, eos.delta, eos.epsilon, eos.a_alpha)
    Vs_slow = eos.volume_solutions(299, 1E6, eos.b, eos.delta, eos.epsilon, eos.a_alpha, quick=False)
    Vs_expected = [(0.00013017554170570767+0j), (0.0011236546051852433+0.0012949262365671505j), (0.0011236546051852433-0.0012949262365671505j)]

    assert_allclose(Vs_fast, Vs_expected)
    assert_allclose(Vs_slow, Vs_expected)
    
    # Test of a_alphas
    a_alphas = (3.8069848647566698, -0.006971714700883658, 2.366703486824857e-05)
    a_alphas_fast = eos.a_alpha_and_derivatives(299)
    assert_allclose(a_alphas, a_alphas_fast)
    a_alphas_slow = eos.a_alpha_and_derivatives(299, quick=False)
    assert_allclose(a_alphas, a_alphas_slow)
    [assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False, quick=i), rtol=1e-12) for i in (True, False)]

    # back calculation for T
    eos = TWUPRMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], V=0.00013017554170570767, P=1E6)
    assert_allclose(eos.T, 299)
    T_slow = eos.solve_T(P=1E6, V=0.00013017554170570767, quick=False)
    assert_allclose(T_slow, 299)

    
    eos = TWUPRMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., P=1E6)
    # Derivatives
    diffs_1, diffs_2, diffs_mixed, departures = ([592877.7698667824, -3683684905961.741, 1.6094692814449423e-07, -2.7146730122915294e-13, 6213228.245662597, 1.6866883037707698e-06], 
                                                 [-708.1014081968287, 4.512485403434166e+17, 1.1685466035091765e-09, 9.027518486599707e-21, -280283776931.3797, 3.3978167906790706e-15], 
                                                 [-3.823707450118526e-15, -20741136287.632187, 0.0715233066523022], 
                                                 [-31652.73712017438, -74.1128504294285, 35.18913741045412])
    known_derivs_deps = [diffs_1, diffs_2, diffs_mixed, departures]
    
    for f in [True, False]:
        main_calcs = eos.derivatives_and_departures(eos.T, eos.P, eos.V_l, eos.b, eos.delta, eos.epsilon, eos.a_alpha, eos.da_alpha_dT, eos.d2a_alpha_dT2, quick=f)
        main_calcs = (main_calcs[0:6], main_calcs[6:12], main_calcs[12:15], main_calcs[15:])
        for i, j in zip(known_derivs_deps, main_calcs):
            assert_allclose(i, j)
        
    # Integration tests
    eos = TWUPRMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., V=0.00013)
    fast_vars = vars(eos)
    eos.set_properties_from_solution(eos.T, eos.P, eos.V, eos.b, eos.delta, eos.epsilon, eos.a_alpha, eos.da_alpha_dT, eos.d2a_alpha_dT2, quick=False)
    slow_vars = vars(eos)
    [assert_allclose(slow_vars[i], j) for (i, j) in fast_vars.items() if isinstance(j, float)]

    # Superctitical test
    eos = TWUPRMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=900., P=1E6)
    eos = TWUPRMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], V=0.007371700581036866, P=1E6)
    assert_allclose(eos.T, 900)


def test_TWUPRMIX_quick():
    # Two-phase nitrogen-methane
    eos = TWUPRMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    Vs_expected = [3.6245710416906234e-05, 0.00019407217464617227, 0.0007004401318229851]
    assert_allclose(eos.sorted_volumes, Vs_expected)

    # Test of a_alphas
    a_alphas = (0.21887744827068994, -0.0006338028987948183, 3.358462881663777e-06)
    a_alphas_fast = eos.a_alpha_and_derivatives(115)
    assert_allclose(a_alphas, a_alphas_fast)
    a_alphas_slow = eos.a_alpha_and_derivatives(115, quick=False)
    assert_allclose(a_alphas, a_alphas_slow)
    [assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False, quick=i), rtol=1e-12) for i in (True, False)]

    # back calculation for T, both solutions
    for V in [3.624571041690618e-05, 0.0007004401318229852]:
        eos = TWUPRMIX(V=V, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
        assert_allclose(eos.T, 115)
        T_slow = eos.solve_T(P=1E6, V=V, quick=False)
        assert_allclose(T_slow, 115)


    # Fugacities
    eos = TWUPRMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(eos.phis_l, [1.5843100443266374, 0.14661177659453567])
    assert_allclose(eos.phis_g, [0.8729379355284885, 0.716098499114619])
    
    # Numerically test fugacities at one point
    def numerical_fugacity_coefficient(n1, n2=0.5, switch=False, l=True):
        if switch:
            n1, n2 = n2, n1
        tot = n1+n2
        zs = [i/tot for i in [n1,n2]]
        a = TWUPRMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=zs, kijs=[[0,0],[0,0]])
        phi = a.phi_l if l else a.phi_g
        return tot*log(phi)

    phis = [[derivative(numerical_fugacity_coefficient, 0.5, dx=1E-6, order=25, args=(0.5, i, j)) for i in [False, True]] for j in [False, True]]
    assert_allclose(phis, [eos.lnphis_g, eos.lnphis_l])

    # Gas phase only test point
    eos = TWUPRMIX(T=300, P=1E7, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(eos.phis_g, [0.97697895693183, 0.8351530876083071]) 


def test_TWUSRKMIX_vs_TWUSRK():
    # Test solution for molar volumes
    eos = TWUSRKMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., P=1E6)
    Vs_expected = [0.00014689222296622505, (0.0011695660499307966-0.00130117826309488j), (0.0011695660499307966+0.00130117826309488j)]
    assert_allclose(eos.sorted_volumes, Vs_expected)
    
    # Test of a_alphas
    a_alphas = (3.7196696151053654, -0.00726972623757774, 2.3055902218261955e-05)
    a_alphas_fast = eos.a_alpha_and_derivatives(299)
    assert_allclose(a_alphas, a_alphas_fast)
    a_alphas_slow = eos.a_alpha_and_derivatives(299, quick=False)
    assert_allclose(a_alphas, a_alphas_slow)
    [assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False, quick=i), rtol=1e-12) for i in (True, False)]

    # back calculation for T
    eos = TWUSRKMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], V=0.00014689222296622483, P=1E6)
    assert_allclose(eos.T, 299)
    T_slow = eos.solve_T(P=1E6, V=0.00014689222296622483, quick=False)
    assert_allclose(T_slow, 299)

    
    eos = TWUSRKMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., P=1E6)
    # Derivatives
    diffs_1, diffs_2, diffs_mixed, departures = ([504446.40946384973, -2676840643946.846, 1.884484272922847e-07, -3.735747222238669e-13, 5306491.618786469, 1.982371132471433e-06], 
                                                 [-586.1645169279951, 2.662434043919377e+17, 1.3088622396059171e-09, 1.388069796850075e-20, -195576372405.25793, 4.566404923205759e-15], 
                                                 [-5.0154055805868715e-15, -14235383353.785719, 0.06816568099016031], 
                                                 [-31612.602587050424, -74.02296609322131, 34.24267346218357])
    known_derivs_deps = [diffs_1, diffs_2, diffs_mixed, departures]
    
    for f in [True, False]:
        main_calcs = eos.derivatives_and_departures(eos.T, eos.P, eos.V_l, eos.b, eos.delta, eos.epsilon, eos.a_alpha, eos.da_alpha_dT, eos.d2a_alpha_dT2, quick=f)
        main_calcs = (main_calcs[0:6], main_calcs[6:12], main_calcs[12:15], main_calcs[15:])
        for i, j in zip(known_derivs_deps, main_calcs):
            assert_allclose(i, j)
    
    # Integration tests
    eos = TWUSRKMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299.,V=0.00013)
    fast_vars = vars(eos)
    eos.set_properties_from_solution(eos.T, eos.P, eos.V, eos.b, eos.delta, eos.epsilon, eos.a_alpha, eos.da_alpha_dT, eos.d2a_alpha_dT2, quick=False)
    slow_vars = vars(eos)
    [assert_allclose(slow_vars[i], j) for (i, j) in fast_vars.items() if isinstance(j, float)]

    # Superctitical test
    eos = TWUSRKMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=900., P=1E6)
    eos = TWUSRKMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], V=0.007422212960199866, P=1E6)
    assert_allclose(eos.T, 900)


def test_TWUSRKMIX_quick():
    # Two-phase nitrogen-methane
    eos = TWUSRKMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    Vs_expected = [4.108792754297656e-05, 0.0002033679482866679, 0.000711707325257978]
    assert_allclose(eos.sorted_volumes, Vs_expected)

    # Test of a_alphas
    a_alphas = (0.2101906113921238, -0.0007322002407973534, 2.600317479929538e-06)
    a_alphas_fast = eos.a_alpha_and_derivatives(115)
    assert_allclose(a_alphas, a_alphas_fast)
    a_alphas_slow = eos.a_alpha_and_derivatives(115, quick=False)
    assert_allclose(a_alphas, a_alphas_slow)
    [assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False, quick=i), rtol=1e-12) for i in (True, False)]

    # back calculation for T, both solutions
    for V in [4.108792754297647e-05, 0.0007117073252579778]:
        eos = TWUSRKMIX(V=V, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
        assert_allclose(eos.T, 115)
        T_slow = eos.solve_T(P=1E6, V=V, quick=False)
        assert_allclose(T_slow, 115)


    # Fugacities
    eos = TWUSRKMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(eos.phis_l, [1.6193856616533904, 0.14818727763145562])
    assert_allclose(eos.phis_g, [0.8835668629797101, 0.7249406348215529])
    
    # Numerically test fugacities at one point
    def numerical_fugacity_coefficient(n1, n2=0.5, switch=False, l=True):
        if switch:
            n1, n2 = n2, n1
        tot = n1+n2
        zs = [i/tot for i in [n1,n2]]
        a = TWUSRKMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=zs, kijs=[[0,0],[0,0]])
        phi = a.phi_l if l else a.phi_g
        return tot*log(phi)

    phis = [[derivative(numerical_fugacity_coefficient, 0.5, dx=1E-6, order=25, args=(0.5, i, j)) for i in [False, True]] for j in [False, True]]
    assert_allclose(phis, [eos.lnphis_g, eos.lnphis_l])

    # Gas phase only test point
    eos = TWUSRKMIX(T=300, P=1E7, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(eos.phis_g, [1.0172098207387374, 0.8799658237051876]) 


def test_APISRKMIX_vs_APISRK():
    # Test solution for molar volumes
    eos = APISRKMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., P=1E6)
    Vs_fast = eos.volume_solutions(299, 1E6, eos.b, eos.delta, eos.epsilon, eos.a_alpha)
    Vs_slow = eos.volume_solutions(299, 1E6, eos.b, eos.delta, eos.epsilon, eos.a_alpha, quick=False)
    Vs_expected = [(0.00014681828835112518+0j), (0.0011696030172383468+0.0013042038361510636j), (0.0011696030172383468-0.0013042038361510636j)]
    assert_allclose(Vs_fast, Vs_expected)
    assert_allclose(Vs_slow, Vs_expected)
    
    # Test of a_alphas
    a_alphas = (3.727476773890392, -0.007334914894987986, 1.9482553059883725e-05)
    a_alphas_fast = eos.a_alpha_and_derivatives(299)
    assert_allclose(a_alphas, a_alphas_fast)
    a_alphas_slow = eos.a_alpha_and_derivatives(299, quick=False)
    assert_allclose(a_alphas, a_alphas_slow)
    [assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False, quick=i), rtol=1e-12) for i in (True, False)]

    # SRK back calculation for T
    eos = APISRKMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], V=0.00014681828835112518, P=1E6)
    assert_allclose(eos.T, 299)
    T_slow = eos.solve_T(P=1E6, V=0.00014681828835112518, quick=False)
    assert_allclose(T_slow, 299)
    # with a S1 set
    # NOTE! There is another solution to the below case with T=2.9237332747177884 K. Prefer not to return it.
    eos = APISRKMIX(Tcs=[514.0], Pcs=[6137000], zs=[1], S1s=[1.678665], S2s=[-0.216396], P=1E6, V=7.045695070282895e-05)
    assert_allclose(eos.T, 299)
    eos = APISRKMIX(Tcs=[514.0], Pcs=[6137000], zs=[1], omegas=[0.635], S2s=[-0.216396], P=1E6, V=7.184693818446427e-05)
    assert_allclose(eos.T, 299)
    
    T_slow = eos.solve_T(P=1E6, V=7.184693818446427e-05, quick=False)
    assert_allclose(T_slow, 299)

    
    eos = APISRKMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., P=1E6)
    # Derivatives
    diffs_1 = [507160.1972586132, -2694518622391.442, 1.882192214387065e-07, -3.7112380359519615e-13, 5312953.652428371, 1.9717635678142066e-06]
    diffs_2 = [-495.70334320516093, 2.6860475503881738e+17, 1.3462140892058854e-09, 1.3729987070697146e-20, -201893442624.31924, 3.80002419401763e-15]
    diffs_mixed = [-4.990229443299593e-15, -14325363284.978655, 0.06593412205681572]
    departures = [-31759.40804708375, -74.3842308177361, 28.946481902635792]
    known_derivs_deps = [diffs_1, diffs_2, diffs_mixed, departures]
    
    for f in [True, False]:
        main_calcs = eos.derivatives_and_departures(eos.T, eos.P, eos.V_l, eos.b, eos.delta, eos.epsilon, eos.a_alpha, eos.da_alpha_dT, eos.d2a_alpha_dT2, quick=f)
        main_calcs = (main_calcs[0:6], main_calcs[6:12], main_calcs[12:15], main_calcs[15:])
        for i, j in zip(known_derivs_deps, main_calcs):
            assert_allclose(i, j)
            
    # Integration tests
    eos = APISRKMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299.,V=0.00013)
    fast_vars = vars(eos)
    eos.set_properties_from_solution(eos.T, eos.P, eos.V, eos.b, eos.delta, eos.epsilon, eos.a_alpha, eos.da_alpha_dT, eos.d2a_alpha_dT2, quick=False)
    slow_vars = vars(eos)
    [assert_allclose(slow_vars[i], j) for (i, j) in fast_vars.items() if isinstance(j, float)]
    
    # Test vs. pure with S1, S2
    eos = APISRKMIX(Tcs=[514.0], Pcs=[6137000], omegas=[0.2975], zs=[1], S1s=[1.678665], S2s=[-0.216396], P=1E6, T=299)
    alphas_mix = eos.a_alpha_and_derivatives(eos.T)
    alphas_expect = (2.253839504404085, -0.005643991699455514, 1.1130938936120253e-05)
    alphas_pure = eos.pures()[0].a_alpha_and_derivatives(eos.T)
    assert_allclose(alphas_expect, alphas_mix, rtol=1e-12)
    assert_allclose(alphas_pure, alphas_mix, rtol=1e-12)


def test_APISRKMIX_quick():
    # Two-phase nitrogen-methane
    eos = APISRKMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    Vs_expected = [4.10159231077475e-05, 0.000204678447676427, 0.0007104688303034479]
    assert_allclose(eos.sorted_volumes, Vs_expected)

    # Test of a_alphas
    a_alphas = (0.2108068740329283, -0.0007639202977930443, 4.705536792825722e-06)
    a_alphas_fast = eos.a_alpha_and_derivatives(115)
    assert_allclose(a_alphas, a_alphas_fast)
    a_alphas_slow = eos.a_alpha_and_derivatives(115, quick=False)
    assert_allclose(a_alphas, a_alphas_slow)
    [assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False, quick=i), rtol=1e-12) for i in (True, False)]

    # back calculation for T, both solutions
    for V in [4.1015923107747434e-05, 0.0007104688303034478]:
        eos = APISRKMIX(V=V, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
        assert_allclose(eos.T, 115)
        T_slow = eos.solve_T(P=1E6, V=V, quick=False)
        assert_allclose(T_slow, 115)


    # Fugacities
    eos = APISRKMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(eos.phis_l, [1.6357646066980698, 0.14324096476246728])
    assert_allclose(eos.phis_g, [0.8843165822638349, 0.7230395975514106])
    
    # Numerically test fugacities at one point
    def numerical_fugacity_coefficient(n1, n2=0.5, switch=False, l=True):
        if switch:
            n1, n2 = n2, n1
        tot = n1+n2
        zs = [i/tot for i in [n1,n2]]
        a = APISRKMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=zs, kijs=[[0,0],[0,0]])
        phi = a.phi_l if l else a.phi_g
        return tot*log(phi)

    phis = [[derivative(numerical_fugacity_coefficient, 0.5, dx=1E-6, order=25, args=(0.5, i, j)) for i in [False, True]] for j in [False, True]]
    assert_allclose(phis, [eos.lnphis_g, eos.lnphis_l])

    # Gas phase only test point
    a = APISRKMIX(T=300, P=1E7, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(a.phis_g, [1.020708538988692, 0.8725461195162044]) 
    
    base = APISRKMIX(T=300, P=1E7, Tcs=[126.1], Pcs=[33.94E5], omegas=[0.04], zs=[1])
    assert base.P_max_at_V(base.V_g) is None

def test_RKMIX_quick():
    # Two-phase nitrogen-methane
    eos = RKMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    
    Vs_calc = eos.sorted_volumes
    Vs_expected = [4.04841478191211e-05, 0.00021507299462855748, 0.0007006060586399438]
    assert_allclose(Vs_calc, Vs_expected)
    
    # Test of a_alphas
    a_alphas = (0.21560553557204304, -0.0009374153720523612, 1.2227157026769929e-05)
    a_alphas_fast = eos.a_alpha_and_derivatives(115)
    assert_allclose(a_alphas, a_alphas_fast)
    a_alphas_slow = eos.a_alpha_and_derivatives(115, quick=False)
    assert_allclose(a_alphas, a_alphas_slow)
    [assert_allclose(a_alphas[0], eos.a_alpha_and_derivatives(eos.T, full=False, quick=i), rtol=1e-12) for i in (True, False)]

    # back calculation for T, both solutions
    for V in [4.04841478191211e-05, 0.0007006060586399438]:
        eos = RKMIX(V=V, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
        assert_allclose(eos.T, 115)
        T_slow = eos.solve_T(P=1E6, V=V, quick=False)
        assert_allclose(T_slow, 115)
    
    # Fugacities
    eos = RKMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert_allclose(eos.phis_l, [1.690029818231663, 0.11498701813658066])
    assert_allclose(eos.phis_g, [0.8872543290701194, 0.7106636262058122])
    assert_allclose(eos.fugacities_l ,[845014.9091158316, 57493.50906829033])
    assert_allclose(eos.fugacities_g, [443627.1645350597, 355331.8131029061])
    
    # Test solve_T for pure component but a mixture (also PV)
    obj = RKMIX(T=115, P=1E6, Tcs=[126.1], Pcs=[33.94E5], omegas=[0.04], zs=[1.0])
    for V in [5.9099600832651364e-05, 0.0008166666387475041]:
        eos = obj.to(V=V, P=obj.P, zs=[1.0])
        assert_allclose(eos.T, 115)
        T_slow = eos.solve_T(P=1E6, V=V, quick=False)
        assert_allclose(T_slow, 115)
    
        eos = obj.to(V=V, T=obj.T, zs=[1.0])
        assert_allclose(eos.P, obj.P)
    
    # Check the a_alphas are the same
    pure_obj = obj.pures()[0]
    assert_allclose([obj.a_alpha, obj.da_alpha_dT, obj.d2a_alpha_dT2], 
                    [pure_obj.a_alpha, pure_obj.da_alpha_dT, pure_obj.d2a_alpha_dT2], rtol=1e-12)

    # This low T, P one failed to create before
    RKMIX(Tcs=[768.0], Pcs=[1070000.0], omegas=[0.8805], kijs=[[0.0]], zs=[1.0], T=0.0001, P=1e-60, fugacities=False)
    RKMIX(Tcs=[768.0], Pcs=[1070000.0], omegas=[0.8805], kijs=[[0.0]], zs=[1.0], T=0.0001, P=1e-60, fugacities=True)


def test_PRMIXTranslatedConsistent_vs_pure():
    # Test solution for molar volumes
    eos = PRMIXTranslatedConsistent(Tcs=[33.2], Pcs=[1296960.0], omegas=[-0.22], zs=[1], T=300, P=1e6)
    eos_pure = PRTranslatedConsistent(Tc=33.2, Pc=1296960.0, omega=-0.22, T=300, P=1e6)
    eos_pure_copy = eos.pures()[0]
    assert_allclose(eos_pure.sorted_volumes, eos.sorted_volumes, rtol=1e-13)
    assert_allclose(eos_pure_copy.sorted_volumes, eos.sorted_volumes, rtol=1e-13)
    
    # Test of a_alphas
    a_alphas_expect = (0.0002908980675477252, -7.343408956556013e-06, 1.6748923735113275e-07)
    a_alphas = eos.a_alpha_and_derivatives(eos.T)
    a_alphas_pure = eos_pure.a_alpha_and_derivatives(eos_pure.T)
    assert_allclose(a_alphas, a_alphas_expect, rtol=1e-12)
    assert_allclose(a_alphas, a_alphas_pure, rtol=1e-12)
    
    # Test of PV
    eos_PV = eos.to(P=eos.P, V=eos.V_l, zs=eos.zs)
    eos_pure_PV = eos_pure.to(P=eos.P, V=eos.V_l)
    assert_allclose(eos_PV.T, eos.T, rtol=1e-9)
    assert_allclose(eos_pure_PV.T, eos.T, rtol=1e-9)

    # Test of TV
    eos_TV = eos.to(T=eos.T, V=eos.V_l, zs=eos.zs)
    eos_pure_TV = eos_pure.to(T=eos.T, V=eos.V_l)
    assert_allclose(eos_TV.P, eos.P, rtol=1e-9)
    assert_allclose(eos_pure_TV.P, eos.P, rtol=1e-9)
    
    # Test c
    assert_allclose(eos.c, eos_pure.c, rtol=1e-12)
    assert_allclose(eos_pure_copy.c, eos.c, rtol=1e-12)

    # Test Psat
    assert_allclose(eos.Psat(eos.T), eos_pure.Psat(eos.T), rtol=1e-9)

    # Fugacity - need derivatives right; go to gas point to make the difference bigger
    T = 50
    eos = PRMIXTranslatedConsistent(Tcs=[33.2], Pcs=[1296960.0], omegas=[-0.22], zs=[1], T=T, P=1e6)
    eos_pure = PRTranslatedConsistent(Tc=33.2, Pc=1296960.0, omega=-0.22, T=T, P=1e6)
    assert_allclose(eos.phis_g[0], eos_pure.phi_g, rtol=1e-12)
    
    # Misc points
    mech_crit = eos.to_mechanical_critical_point()
    assert_allclose([mech_crit.T, mech_crit.P], [eos.Tcs[0], eos.Pcs[0]])
    
    # Different test where a_alpha is zero - first term solution
    alpha_zero = PRMIXTranslatedConsistent(Tcs=[33.2], Pcs=[1296960.0], omegas=[-0.22], kijs=[[0.0]], zs=[1], T=6000, P=1e2)
    assert 0.0 == alpha_zero.a_alpha
    assert_allclose(alpha_zero.V_l, 498.86777507259984, rtol=1e-12)
    assert_allclose(alpha_zero.V_l, alpha_zero.b + R*alpha_zero.T/alpha_zero.P, rtol=1e-12)
    assert eos.P_max_at_V(1) is None # No direct solution for P


def test_PRMIXTranslatedPPJP_vs_pure():
    eos = PRMIXTranslatedPPJP(Tcs=[33.2], Pcs=[1296960.0], omegas=[-0.22], zs=[1], T=300, P=1e6, cs=[-1.4256e-6])
    eos_pure = PRTranslatedPPJP(Tc=33.2, Pc=1296960.0, omega=-0.22, T=300, P=1e6, c=-1.4256e-6)
    eos_pure_copy = eos.pures()[0]
    assert_allclose(eos_pure.sorted_volumes, eos.sorted_volumes, rtol=1e-13)
    assert_allclose(eos_pure_copy.sorted_volumes, eos.sorted_volumes, rtol=1e-13)
    Vs_expect = [-2.7557919524404116e-05, 5.90161172350635e-06, 0.0025037140652460132]
    assert_allclose(Vs_expect, eos.sorted_volumes)
    
    # Test of a_alphas
    a_alphas_expect = (0.021969565519583095, -1.16079431214164e-05, 2.2413185621355093e-08)
    a_alphas = eos.a_alpha_and_derivatives(eos.T)
    a_alphas_pure = eos_pure.a_alpha_and_derivatives(eos_pure.T)
    assert_allclose(a_alphas, a_alphas_expect, rtol=1e-12)
    assert_allclose(a_alphas, a_alphas_pure, rtol=1e-12)
    
    # Test of PV
    eos_PV = eos.to(P=eos.P, V=eos.V_l, zs=eos.zs)
    eos_pure_PV = eos_pure.to(P=eos.P, V=eos.V_l)
    assert_allclose(eos_PV.T, eos.T, rtol=1e-9)
    assert_allclose(eos_pure_PV.T, eos.T, rtol=1e-9)
    
    # Test of TV
    eos_TV = eos.to(T=eos.T, V=eos.V_l, zs=eos.zs)
    eos_pure_TV = eos_pure.to(T=eos.T, V=eos.V_l)
    assert_allclose(eos_TV.P, eos.P, rtol=1e-9)
    assert_allclose(eos_pure_TV.P, eos.P, rtol=1e-9)
    
    # Test c
    assert_allclose(eos.c, eos_pure.c, rtol=1e-12)
    assert_allclose(eos_pure_copy.c, eos.c, rtol=1e-12)
    
    # Test Psat
    assert_allclose(eos.Psat(eos.T), eos_pure.Psat(eos.T), rtol=1e-9)
    
    T = 50
    eos = PRMIXTranslatedPPJP(Tcs=[33.2], Pcs=[1296960.0], omegas=[-0.22], zs=[1], T=T, P=1e6, cs=[-1.4256e-6])
    eos_pure = PRTranslatedPPJP(Tc=33.2, Pc=1296960.0, omega=-0.22, T=T, P=1e6, c=-1.4256e-6)
    assert_allclose(eos.phis_g[0], eos_pure.phi_g, rtol=1e-12)


def test_SRKMIXTranslatedConsistent_vs_pure():
    # Test solution for molar volumes
    eos = SRKMIXTranslatedConsistent(Tcs=[33.2], Pcs=[1296960.0], omegas=[-0.22], zs=[1], T=300, P=1e6)
    eos_pure = SRKTranslatedConsistent(Tc=33.2, Pc=1296960.0, omega=-0.22, T=300, P=1e6)
    eos_pure_copy = eos.pures()[0]
    assert_allclose(eos_pure.sorted_volumes, eos.sorted_volumes, rtol=1e-13)
    assert_allclose(eos_pure_copy.sorted_volumes, eos.sorted_volumes, rtol=1e-13)
    
    # Test of a_alphas
    a_alphas_expect = (1.281189532964332e-05, -5.597692089837639e-07, 2.3057572995770314e-08)
    a_alphas = eos.a_alpha_and_derivatives(eos.T)
    a_alphas_pure = eos_pure.a_alpha_and_derivatives(eos_pure.T)
    assert_allclose(a_alphas, a_alphas_expect, rtol=1e-12)
    assert_allclose(a_alphas, a_alphas_pure, rtol=1e-12)
    
    # Test of PV
    eos_PV = eos.to(P=eos.P, V=eos.V_l, zs=eos.zs)
    eos_pure_PV = eos_pure.to(P=eos.P, V=eos.V_l)
    assert_allclose(eos_PV.T, eos.T, rtol=1e-9)
    assert_allclose(eos_pure_PV.T, eos.T, rtol=1e-9)
    
    # Test of TV
    eos_TV = eos.to(T=eos.T, V=eos.V_l, zs=eos.zs)
    eos_pure_TV = eos_pure.to(T=eos.T, V=eos.V_l)
    assert_allclose(eos_TV.P, eos.P, rtol=1e-9)
    assert_allclose(eos_pure_TV.P, eos.P, rtol=1e-9)
    
    # Test c
    assert_allclose(eos.c, eos_pure.c, rtol=1e-12)
    assert_allclose(eos_pure_copy.c, eos.c, rtol=1e-12)
    
    # Test Psat
    assert_allclose(eos.Psat(eos.T), eos_pure.Psat(eos.T), rtol=1e-9)
    
    # Fugacity - need derivatives right; go to gas point to make the difference bigger
    T = 50
    eos = SRKMIXTranslatedConsistent(Tcs=[33.2], Pcs=[1296960.0], omegas=[-0.22], zs=[1], T=T, P=1e6)
    eos_pure = SRKTranslatedConsistent(Tc=33.2, Pc=1296960.0, omega=-0.22, T=T, P=1e6)
    assert_allclose(eos.phis_g[0], eos_pure.phi_g, rtol=1e-12)
    
    
    # Misc points
    mech_crit = eos.to_mechanical_critical_point()
    assert_allclose([mech_crit.T, mech_crit.P], [eos.Tcs[0], eos.Pcs[0]])
    
    alpha_zero = SRKMIXTranslatedConsistent(Tcs=[33.2], Pcs=[1296960.0], omegas=[-0.22], kijs=[[0.0]], zs=[1], T=6000, P=1e2)
    assert 0.0 == alpha_zero.a_alpha
    
    # Different test where a_alpha is zero - first term solution
    assert_allclose(alpha_zero.V_l, 498.8677735227847, rtol=1e-12)
    assert_allclose(alpha_zero.V_l, alpha_zero.b + R*alpha_zero.T/alpha_zero.P, rtol=1e-12)
    assert eos.P_max_at_V(1) is None # No direct solution for P


@pytest.mark.slow
@pytest.mark.CoolProp
def test_fugacities_PR_vs_coolprop():
    import CoolProp.CoolProp as CP
        
    zs = [0.4, 0.6]
    Tcs = [305.322, 540.13]
    Pcs = [4872200.0, 2736000.0]
    omegas = [0.099, 0.349]
    kij = .0067
    kijs = [[0,kij],[kij,0]]
    c1, c2 = PRMIX.c1, PRMIX.c2
    # match coolprop
    PRMIX.c1, PRMIX.c2 = 0.45724, 0.07780

    T, P = 300, 1e5
    eos = PRMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)

    AS = CP.AbstractState("PR", "Ethane&Heptane")
    AS.set_mole_fractions(zs)
    AS.set_binary_interaction_double(0,1,"kij", kij)
    AS.update(CP.PT_INPUTS, P, T)

    fugacities_CP = [AS.fugacity(0), AS.fugacity(1)]
    assert_allclose(fugacities_CP, eos.fugacities_g, rtol=1e-13)

    T, P = 300, 1e6
    eos = PRMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    AS.update(CP.PT_INPUTS, P, T)
    fugacities_CP = [AS.fugacity(0), AS.fugacity(1)]
    assert_allclose(fugacities_CP, eos.fugacities_l, rtol=1e-13)
    
    # Set the coefficients back
    PRMIX.c1, PRMIX.c2 = c1, c2


@pytest.mark.slow
@pytest.mark.CoolProp
def test_fugacities_SRK_vs_coolprop():
    import CoolProp.CoolProp as CP
    zs = [0.4, 0.6]
    Tcs = [305.322, 540.13]
    Pcs = [4872200.0, 2736000.0]
    omegas = [0.099, 0.349]
    kij = .0067
    kijs = [[0,kij],[kij,0]]
    c1, c2 = SRKMIX.c1, SRKMIX.c2
    # match coolprop
    SRKMIX.c1, SRKMIX.c2 = 0.42747, 0.08664
    
    T, P = 300, 1e5
    eos = SRKMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    
    AS = CP.AbstractState("SRK", "Ethane&Heptane")
    AS.set_mole_fractions(zs)
    AS.set_binary_interaction_double(0,1,"kij", kij)
    AS.update(CP.PT_INPUTS, P, T)
    
    fugacities_CP = [AS.fugacity(0), AS.fugacity(1)]
    assert_allclose(fugacities_CP, eos.fugacities_g, rtol=1e-13)
    
    T, P = 300, 1e6
    eos = SRKMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    AS.update(CP.PT_INPUTS, P, T)
    fugacities_CP = [AS.fugacity(0), AS.fugacity(1)]
    assert_allclose(fugacities_CP, eos.fugacities_l, rtol=1e-13)
    
    # Set the coefficients back
    SRKMIX.c1, SRKMIX.c2 = c1, c2


def test_Z_derivative_T():
    from fluids.constants import R
    T = 115
    dT = 1e-5
    P = 1e6
    eos1 = PRMIX(T=T, P=P, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    eos2 = PRMIX(T=T+dT, P=P, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    
    dZ_dT_numerical = (eos2.Z_g - eos1.Z_g)/dT
    dZ_dT_analytical = P/R*(-eos1.V_g*T**-2 + eos1.dV_dT_g/T)
    
    assert_allclose(dZ_dT_numerical, dZ_dT_analytical, rtol=1e-6)
    assert_allclose(eos1.dZ_dT_g, 0.008538861194633872, rtol=1e-11)
    
    dZ_dT_numerical = (eos2.Z_l - eos1.Z_l)/dT
    dZ_dT_analytical = P/R*(-eos1.V_l*T**-2 + eos1.dV_dT_l/T)
    
    assert_allclose(dZ_dT_numerical, dZ_dT_analytical, rtol=1e-5)
    assert_allclose(eos1.dZ_dT_l, -5.234447550711918e-05, rtol=1e-11)
    
def test_Z_derivative_P():
    from fluids.constants import R

    T = 115
    dP = 1e-2
    P = 1e6
    eos1 = PRMIX(T=T, P=P, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    eos2 = PRMIX(T=T, P=P + dP, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    
    dZ_dP_numerical = (eos2.Z_g - eos1.Z_g)/dP
    dZ_dP_analytical = 1/(T*R)*(eos1.V_g + P*eos1.dV_dP_g)
    
    assert_allclose(dZ_dP_analytical, dZ_dP_numerical)
    assert_allclose(eos1.dZ_dP_g, dZ_dP_numerical)
    
    dZ_dP_numerical = (eos2.Z_l - eos1.Z_l)/dP
    dZ_dP_analytical = 1/(T*R)*(eos1.V_l + P*eos1.dV_dP_l)
    
    assert_allclose(dZ_dP_analytical, dZ_dP_numerical)
    assert_allclose(eos1.dZ_dP_l, dZ_dP_numerical)
    
def test_PR_d_lbphis_dT():
    dT = 1e-6
    T = 270.0
    P = 76E5
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    zs = [0.3, 0.1, 0.6]
    
    eos = eos1 = PRMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    eos2 = PRMIX(T=T + dT, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    numerical_diffs = (np.array(eos2.lnphis_g) - eos1.lnphis_g) / dT
    
    
    expected_diffs = [-0.0125202946344780, -0.00154326287196778, 0.0185468995722353]
    analytical_diffs = eos.dlnphis_dT('g')
    assert_allclose(analytical_diffs, expected_diffs, rtol=1e-11)
    assert_allclose(expected_diffs, numerical_diffs, rtol=1e-5)

    analytical_diffs_generic = super(eos.__class__, eos).dlnphis_dT('g')
    assert_allclose(analytical_diffs, analytical_diffs_generic, rtol=1e-11)

@pytest.mark.sympy
def test_PR_dlnphis_dT_sympy():
    from sympy import Derivative, symbols, sqrt, diff, log, N, Function
    from fluids.constants import R as R_num
    T_num = 270.0
    P_num = 76E5
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    zs = [0.3, 0.1, 0.6]
    
    eos = PRMIX(T=T_num, P=P_num, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    diffs_implemented = eos.dlnphis_dT('g')

    # Symbolic part
    T, P, R, b1, b2, b3, b, = symbols('T, P, R, b1, b2, b3, b')
    Z_f, sum_f, a_alpha_f = symbols('Z_f, sum_f, a_alpha_f', cls=Function)
    
    root_two = sqrt(2)
    two_root_two = 2*sqrt(2)
    a_alpha, sum_fun = a_alpha_f(T), sum_f(T)
    
    A = a_alpha*P/(R*R*T*T)
    B = b*P/(R*T)
    A, B
    
    Z = Z_f(T) # Change to f(P) when doing others
    
    needed = []
    for bi in [b1, b2, b3]:
        t1 = bi/b*(Z - 1) - log(Z - B)
        t2 = 2/a_alpha*sum_fun
        t3 = t1 - A/(two_root_two*B)*(t2 - bi/b)*log((Z + (root_two + 1)*B)/(Z - (root_two - 1)*B))
        needed.append(diff(t3, T))
    
    sympy_diffs = []
    for i in range(3):
        subs = {Derivative(Z_f(T), T): eos.dZ_dT_g, 
                R: R_num, 'b': eos.b,
                Z_f(T): eos.Z_g, 
                a_alpha: eos.a_alpha, 
                Derivative(a_alpha_f(T), T) : eos.da_alpha_dT,
                Derivative(sum_f(T), T): sum([zs[j]*eos.da_alpha_dT_ijs[i][j] for j in eos.cmps]),
                }
        subs1 = {sum_f(T): sum([zs[j]*eos.a_alpha_ijs[i][j] for j in eos.cmps])}
    
        subs2 = {P: eos.P, 
                 T: eos.T,
                 {0: b1, 1:b2, 2:b3}[i]: eos.bs[i]}
    
        working = needed[i].subs(subs)
        working = working.subs(subs1)
        working = working.subs(subs2)
        
        sympy_diffs.append(float(N(working)))
    
    assert_allclose(diffs_implemented, sympy_diffs, rtol=1e-10)
    
def test_SRK_dlnphis_dT():
    dT = 1e-6
    T = 270.0
    P = 76E5
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    zs = [0.3, 0.1, 0.6]
    
    eos = eos1 = SRKMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    eos2 = SRKMIX(T=T + dT, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    numerical_diffs = (np.array(eos2.lnphis_g) - eos1.lnphis_g) / dT
    
    
    expected_diffs = [-0.013492637405729917, -0.002035560753468637, 0.019072382634936852]
    analytical_diffs = eos.dlnphis_dT('g')
    assert_allclose(analytical_diffs, expected_diffs, rtol=1e-11)
    assert_allclose(expected_diffs, numerical_diffs, rtol=1e-5)

    analytical_diffs_generic = super(eos.__class__, eos).dlnphis_dT('g')
    assert_allclose(analytical_diffs, analytical_diffs_generic, rtol=1e-11)


@pytest.mark.sympy
def test_SRK_dlnphis_dT_sympy():
    from sympy import Derivative, symbols, sqrt, diff, log, N, Function
    from fluids.constants import R as R_num
    T_num = 270.0
    P_num = 76E5
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    zs = [0.3, 0.1, 0.6]
    
    eos = SRKMIX(T=T_num, P=P_num, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    diffs_implemented = eos.dlnphis_dT('g')

    # Symbolic part
    T, P, R, b1, b2, b3, b, = symbols('T, P, R, b1, b2, b3, b')
    Z_f, sum_f, a_alpha_f  = symbols('Z_f, sum_f, a_alpha_f', cls=Function)
    a_alpha, sum_fun = a_alpha_f(T), sum_f(T)
    
    A = a_alpha*P/(R*R*T*T)
    B = b*P/(R*T)
    A, B
    
    Z = Z_f(T) # Change to f(P) when doing others
    
    needed = []
    for bi in [b1, b2, b3]:
        Bi = bi*P/R/T
        t1 = Bi/B*(Z-1) - log(Z - B)
        t3 = log(1. + B/Z)
        t2 = A/B*(Bi/B - 2./a_alpha*sum_fun)
        t4 = t1 + t2*t3
        needed.append(diff(t4, T))


    
    sympy_diffs = []
    for i in range(3):
        subs = {Derivative(Z_f(T), T): eos.dZ_dT_g, 
                R: R_num, 'b': eos.b,
                Z_f(T): eos.Z_g, 
                a_alpha: eos.a_alpha, 
                Derivative(a_alpha_f(T), T) : eos.da_alpha_dT,
                Derivative(sum_f(T), T): sum([zs[j]*eos.da_alpha_dT_ijs[i][j] for j in eos.cmps]),
                }
        subs1 = {sum_f(T): sum([zs[j]*eos.a_alpha_ijs[i][j] for j in eos.cmps])}
    
        subs2 = {P: eos.P, 
                 T: eos.T,
                 {0: b1, 1:b2, 2:b3}[i]: eos.bs[i]}
    
        working = needed[i].subs(subs)
        working = working.subs(subs1)
        working = working.subs(subs2)
        
        sympy_diffs.append(float(N(working)))
    
    assert_allclose(diffs_implemented, sympy_diffs, rtol=1e-10)

def test_VDW_dlnphis_dT():
    dT = 1e-5
    T = 280.0 # Need increase T a little
    P = 76E5
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    zs = [0.3, 0.1, 0.6]
    
    eos = eos1 = VDWMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    eos2 = VDWMIX(T=T + dT, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    numerical_diffs = (np.array(eos2.lnphis_g) - eos1.lnphis_g) / dT
    
    expected_diffs =[-0.00457948776557392, 0.000404824835196203, 0.0105772883904069]
    analytical_diffs = eos.dlnphis_dT('g')
    
    assert_allclose(analytical_diffs, expected_diffs, rtol=1e-11)
    assert_allclose(expected_diffs, numerical_diffs, rtol=1e-5)

#    analytical_diffs_generic = super(eos.__class__, eos).dlnphis_dT('g')
#    assert_allclose(analytical_diffs, analytical_diffs_generic, rtol=1e-11)

@pytest.mark.sympy
def test_VDW_dlnphis_dT_sympy():
    from sympy import Derivative, symbols, sqrt, diff, log, N, Function
    from fluids.constants import R as R_num
    T_num = 280.0
    P_num = 76E5
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    zs = [0.3, 0.1, 0.6]
    
    eos = VDWMIX(T=T_num, P=P_num, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    diffs_implemented = eos.dlnphis_dT('g')

    # Symbolic part
    T, P, R, b1, b2, b3, b, = symbols('T, P, R, b1, b2, b3, b')
    a1, a2, a3 = symbols('a1, a2, a3')
    Z_f, sum_f, a_alpha_f = symbols('Z_f, sum_f, a_alpha_f', cls=Function)
    a_alpha, sum_fun = a_alpha_f(T), sum_f(T)
    
    A = a_alpha*P/(R*R*T*T)
    B = b*P/(R*T)
    A, B
    
    Z = Z_f(T) # Change to f(P) when doing others
    
    needed = []
    for ai, bi in zip([a1, a2, a3], [b1, b2, b3]):
        V = Z*R*T/P
        t1 = log(Z*(1 - b/V))
        t2 = 2/(R*T*V)
        t3 = 1/(V - b)
        logphi = (bi*t3 - t1 - t2*sqrt(a_alpha*ai))
        
        needed.append(diff(logphi, T))


    
    sympy_diffs = []
    for i in range(3):
        subs = {Derivative(Z_f(T), T): eos.dZ_dT_g, 
                R: R_num, 'b': eos.b,
                Z_f(T): eos.Z_g, 
                a_alpha: eos.a_alpha, 
                Derivative(a_alpha_f(T), T) : eos.da_alpha_dT,
                Derivative(sum_f(T), T): sum([zs[j]*eos.da_alpha_dT_ijs[i][j] for j in eos.cmps]),
                }
        subs1 = {sum_f(T): sum([zs[j]*eos.a_alpha_ijs[i][j] for j in eos.cmps])}
    
        subs2 = {P: eos.P, 
                 T: eos.T,
                 {0: b1, 1:b2, 2:b3}[i]: eos.bs[i],
                 {0: a1, 1:a2, 2:a3}[i]: eos.ais[i]}
    
        working = needed[i].subs(subs)
        working = working.subs(subs1)
        working = working.subs(subs2)
        
        sympy_diffs.append(float(N(working)))
    
    assert_allclose(diffs_implemented, sympy_diffs, rtol=1e-10)


def test_PR_dlnphis_dP():
    dP = 1e-1
    T = 270.0
    P = 76E5
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    zs = [0.3, 0.1, 0.6]
    
    eos = eos1 = PRMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    eos2 = PRMIX(T=T, P=P + dP, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    numerical_diffs = (np.array(eos2.lnphis_g) - eos1.lnphis_g) / dP
    
    expected_diffs = [8.49254218440054e-8, -3.44512799711331e-9, -1.52343107476988e-7]
    analytical_diffs = eos.dlnphis_dP('g')

    assert_allclose(analytical_diffs, expected_diffs, rtol=1e-11)
    assert_allclose(expected_diffs, numerical_diffs, rtol=1e-5)
    # Base class
    analytical_diffs = super(eos.__class__, eos).dlnphis_dP('g')
    assert_allclose(analytical_diffs, expected_diffs, rtol=1e-11)

@pytest.mark.sympy
def test_PR_dlnphis_dP_sympy():
    from sympy import Derivative, symbols, sqrt, diff, log, N, Function
    from fluids.constants import R as R_num
    T_num = 270.0
    P_num = 76E5
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    zs = [0.3, 0.1, 0.6]
    
    
    eos = PRMIX(T=T_num, P=P_num, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    diffs_implemented = eos.dlnphis_dP('g')

    T, P, R, a_alpha_f, b1, b2, b3, b, = symbols('T, P, R, a_alpha_f, b1, b2, b3, b')
    Z_f, sum_f = symbols('Z_f, sum_f', cls=Function)
    
    root_two = sqrt(2)
    two_root_two = 2*sqrt(2)
    a_alpha, sum_fun = symbols('a_alpha, sum_fun')
    
    A = a_alpha*P/(R*R*T*T)
    B = b*P/(R*T)
    A, B
    
    Z = Z_f(P) # Change to f(P) when doing others
    
    needed = []
    for bi in [b1, b2, b3]:
        t1 = bi/b*(Z - 1) - log(Z - B)
        t2 = 2/a_alpha*sum_fun
        t3 = t1 - A/(two_root_two*B)*(t2 - bi/b)*log((Z + (root_two + 1)*B)/(Z - (root_two - 1)*B))
        needed.append(diff(t3, P))

    sympy_diffs = []
    for i in range(3):
        subs = {Derivative(Z_f(P), P): eos.dZ_dP_g, 
                R: R_num, 'b': eos.b,
                Z_f(P): eos.Z_g, 
                a_alpha: eos.a_alpha, 
                sum_fun: sum([zs[j]*eos.a_alpha_ijs[i][j] for j in eos.cmps])
                }
    
        subs2 = {P: eos.P, 
                 T: eos.T,
                 {0: b1, 1:b2, 2:b3}[i]: eos.bs[i]}
    
        working = needed[i].subs(subs)
        working = working.subs(subs2)
    
        sympy_diffs.append(float((N(working))))
    assert_allclose(sympy_diffs, diffs_implemented, rtol=1e-11)
    
    
def test_SRK_dlnphis_dP():
    dP = 1e-1
    T = 270.0
    P = 76E5
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    zs = [0.3, 0.1, 0.6]
    
    eos = eos1 = SRKMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    eos2 = SRKMIX(T=T, P=P + dP, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    numerical_diffs = (np.array(eos2.lnphis_g) - eos1.lnphis_g) / dP
    
    expected_diffs = [9.40786516520732e-8, 3.03133250647420e-9, -1.51771425140191e-7]
    analytical_diffs = eos.dlnphis_dP('g')
    assert_allclose(analytical_diffs, expected_diffs, rtol=1e-11)
    assert_allclose(expected_diffs, numerical_diffs, rtol=1e-5)

    # Base class
    analytical_diffs = super(eos.__class__, eos).dlnphis_dP('g')
    assert_allclose(analytical_diffs, expected_diffs, rtol=1e-11)

@pytest.mark.sympy
def test_SRK_dlnphis_dP_sympy():
    from sympy import Derivative, symbols, sqrt, diff, log, N, Function
    from fluids.constants import R as R_num
    T_num = 270.0
    P_num = 76E5
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    zs = [0.3, 0.1, 0.6]
    
    eos = SRKMIX(T=T_num, P=P_num, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    diffs_implemented = eos.dlnphis_dP('g')

    T, P, R, b1, b2, b3, b, = symbols('T, P, R, b1, b2, b3, b')
    Z_f, sum_f, a_alpha_f = symbols('Z_f, sum_f, a_alpha_f', cls=Function)
    a_alpha, sum_fun = a_alpha_f(T), sum_f(T)
    
    A = a_alpha*P/(R*R*T*T)
    B = b*P/(R*T)
    A, B
    
    Z = Z_f(P) # Change to f(P) when doing others
    
    needed = []
    for bi in [b1, b2, b3]:
        Bi = bi*P/R/T
        t1 = Bi/B*(Z-1) - log(Z - B)
        t3 = log(1. + B/Z)
        t2 = A/B*(Bi/B - 2./a_alpha*sum_fun)
        t4 = t1 + t2*t3
        needed.append(diff(t4, P))

    sympy_diffs = []
    for i in range(3):
        subs = {Derivative(Z_f(P), P): eos.dZ_dP_g, 
                R: R_num, 'b': eos.b,
                Z_f(P): eos.Z_g, 
                a_alpha: eos.a_alpha, 
                sum_fun: sum([zs[j]*eos.a_alpha_ijs[i][j] for j in eos.cmps])
                }
    
        subs2 = {P: eos.P, 
                 T: eos.T,
                 {0: b1, 1:b2, 2:b3}[i]: eos.bs[i]}
    
        working = needed[i].subs(subs)
        working = working.subs(subs2)
    
        sympy_diffs.append(float((N(working))))
    assert_allclose(sympy_diffs, diffs_implemented, rtol=1e-11)


def test_VDW_dlnphis_dP():
    dP = 1e-1
    T = 280.0 # Need increase T a little
    P = 76E5
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    zs = [0.3, 0.1, 0.6]
    
    eos = eos1 = VDWMIX(T=T, P=P, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    eos2 = VDWMIX(T=T, P=P + dP, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    numerical_diffs = (np.array(eos2.lnphis_g) - eos1.lnphis_g) / dP
    
    expected_diffs = [4.48757918014496e-8, -1.17254464726201e-8, -1.20732168353728e-7]
    analytical_diffs = eos.dlnphis_dP('g')
    
    assert_allclose(analytical_diffs, expected_diffs, rtol=1e-11)
    assert_allclose(expected_diffs, numerical_diffs, rtol=1e-5)

    # Base class - does not pass likely due to zero division error, could use more work
#    analytical_diffs = super(eos.__class__, eos).dlnphis_dP('g')
#    assert_allclose(analytical_diffs, expected_diffs, rtol=1e-11)

@pytest.mark.sympy
def test_VDW_dlnphis_dP_sympy():
    from sympy import Derivative, symbols, sqrt, diff, log, N, Function
    from fluids.constants import R as R_num

    T_num = 280.0
    P_num = 76E5
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    zs = [0.3, 0.1, 0.6]
    
    eos = VDWMIX(T=T_num, P=P_num, Tcs=Tcs, Pcs=Pcs, omegas=omegas, zs=zs, kijs=kijs)
    diffs_implemented = eos.dlnphis_dP('g')

    T, P, R, b1, b2, b3, b, = symbols('T, P, R, b1, b2, b3, b')
    a1, a2, a3 = symbols('a1, a2, a3')
    Z_f, sum_f, a_alpha_f = symbols('Z_f, sum_f, a_alpha_f', cls=Function)
    a_alpha, sum_fun = a_alpha_f(T), sum_f(T)
    
    Z = Z_f(P)
    
    needed = []
    for ai, bi in zip([a1, a2, a3], [b1, b2, b3]):
        V = Z*R*T/P
        t1 = log(Z*(1 - b/V))
        t2 = 2/(R*T*V)
        t3 = 1/(V - b)
        logphi = (bi*t3 - t1 - t2*sqrt(a_alpha*ai))
        
        needed.append(diff(logphi, P))
    
    sympy_diffs = []
    for i in range(3):
        subs = {Derivative(Z_f(P), P): eos.dZ_dP_g, 
                R: R_num, 'b': eos.b,
                Z_f(P): eos.Z_g, 
                a_alpha: eos.a_alpha, 
                sum_f(T): sum([zs[j]*eos.a_alpha_ijs[i][j] for j in eos.cmps])
                }
    
        subs2 = {P: eos.P, 
                 T: eos.T,
                 {0: b1, 1:b2, 2:b3}[i]: eos.bs[i],
                {0: a1, 1:a2, 2:a3}[i]: eos.ais[i]}
    
        working = needed[i].subs(subs)
        working = working.subs(subs2)
        
        sympy_diffs.append(float(N(working)))

    assert_allclose(sympy_diffs, diffs_implemented, rtol=1e-11)



  
def test_dS_dep_dT_liquid_and_vapor():
    T = 115
    P = 1e6
    dT = 1e-4
    zs = [0.5, 0.5]
    eos1 = PRMIX(T=T, P=P, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011],
                zs=zs, kijs=[[0,0],[0,0]])
    eos2 = eos1.to_TP_zs(T=T+dT, P=P, zs=zs)
    
    assert_allclose((eos2.S_dep_l - eos1.S_dep_l)/dT, eos1.dS_dep_dT_l, rtol=1e-6)
    assert_allclose(eos1.dS_dep_dT_l, 0.26620158744414335)
    
    assert_allclose((eos2.S_dep_g - eos1.S_dep_g)/dT, eos1.dS_dep_dT_g, rtol=1e-5)
    assert_allclose(eos1.dS_dep_dT_g, 0.12552871992263925, rtol=1e-5)
    
def test_dH_dep_dT_liquid_and_vapor():
    T = 115
    P = 1e6
    dT = 1e-4
    zs = [0.5, 0.5]
    eos1 = PRMIX(T=T, P=P, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011],
                zs=zs, kijs=[[0,0],[0,0]])
    eos2 = eos1.to_TP_zs(T=T+dT, P=P, zs=zs)
    
    assert_allclose((eos2.H_dep_l - eos1.H_dep_l)/dT, eos1.dH_dep_dT_l, rtol=1e-6)
    assert_allclose(eos1.dH_dep_dT_l, 30.613182556076488)
    
    assert_allclose((eos2.H_dep_g - eos1.H_dep_g)/dT, eos1.dH_dep_dT_g, rtol=1e-5)
    assert_allclose(eos1.dH_dep_dT_g, 14.435802791103512, rtol=1e-5)    
    
    
    
def test_dH_dep_dP_liquid_and_vapor():
    T = 115
    P = 1e6
    dP = 1e-2
    zs = [0.5, 0.5]
    eos1 = PRMIX(T=T, P=P, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011],
                zs=zs, kijs=[[0,0],[0,0]])
    eos2 = eos1.to_TP_zs(T=T, P=P+dP, zs=zs)
    
    assert_allclose((eos2.H_dep_l - eos1.H_dep_l)/dP, eos1.dH_dep_dP_l, rtol=1e-4)
    assert_allclose(eos1.dH_dep_dP_l, 5.755734044915473e-06)
    
    assert_allclose((eos2.H_dep_g - eos1.H_dep_g)/dP, eos1.dH_dep_dP_g, rtol=1e-4)
    assert_allclose(eos1.dH_dep_dP_g, -0.0009389226581529606, rtol=1e-5)
    

def test_dS_dep_dP_liquid_and_vapor():
    T = 115
    P = 1e6
    dP = 1e-2
    zs = [0.5, 0.5]
    eos1 = PRMIX(T=T, P=P, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011],
                zs=zs, kijs=[[0,0],[0,0]])
    eos2 = eos1.to_TP_zs(T=T, P=P+dP, zs=zs)
    
    assert_allclose((eos2.S_dep_l - eos1.S_dep_l)/dP, eos1.dS_dep_dP_l, rtol=1e-5)
    assert_allclose(eos1.dS_dep_dP_l, 8.049231062546365e-06)
    
    assert_allclose((eos2.S_dep_g - eos1.S_dep_g)/dP, eos1.dS_dep_dP_g, rtol=1e-5)
    assert_allclose(eos1.dS_dep_dP_g, -5.942829393044419e-06)
    

### Composition derivatives

ternary_basic = dict(T=300.0, P=1e6, zs=[.7, .2, .1], Tcs=[126.2, 304.2, 373.2],
                     Pcs=[3394387.5, 7376460.0, 8936865.0], omegas=[0.04, 0.2252, 0.1])
quaternary_basic = dict(T=300.0, P=1e5, Tcs=[126.2, 190.564, 304.2, 373.2], 
                        Pcs=[3394387.5, 4599000, 7376460.0, 8936865.0],
                        omegas=[0.04, 0.008, 0.2252, 0.1],
                        zs=[.3, .4, .3-1e-6, 1e-6])



def test_db_dnxpartial():
    liquid_IDs = ['nitrogen', 'carbon dioxide', 'H2S']
    Tcs = [126.2, 304.2, 373.2]
    Pcs = [3394387.5, 7376460.0, 8936865.0]
    omegas = [0.04, 0.2252, 0.1]
    zs = [.7, .2, .1]
    
    normalization = False
    partial_n = False

    def db_dnxpartial(ni, i):
        zs = [.7, .2, .1]
        zs[i] = ni
        nt = sum(zs)
        if normalization:
            zs = normalize(zs)
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        if partial_n:
            return eos.b*nt
        return eos.b
    
    for obj in eos_mix_list:
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        numericals = [derivative(db_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in zip((0, 1, 2), (.7, .2, .1))]
        assert_allclose(numericals, eos.db_dzs)
        
    normalization = True

    for obj in eos_mix_list:
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        numericals = [derivative(db_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in zip((0, 1, 2), (.7, .2, .1))]
        assert_allclose(numericals, eos.db_dns)
    
    partial_n = True
    for obj in eos_mix_list:
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        numericals = [derivative(db_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in zip((0, 1, 2), (.7, .2, .1))]
        assert_allclose(numericals, eos.dnb_dns)

#test_db_dnxpartial()


@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_d2b_d2nx(kwargs):
    kwargs = kwargs.copy()
    zs = kwargs['zs']
    del kwargs['zs'] 
    normalization = False
    
    def d2b_d2nxpartial(comp):
        if normalization:
            comp = normalize(comp)
        eos = obj(zs=comp, **kwargs)
        return eos.b
    
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = hessian(d2b_d2nxpartial, zs, perturbation=1e-4)
        analytical = eos.d2b_dzizjs
        # All zeros if the model is correct
        assert_allclose(numericals, analytical, rtol=1e-6, atol=1e-10)
    
    normalization = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = hessian(d2b_d2nxpartial, zs, perturbation=5e-5)
        analytical = eos.d2b_dninjs
        assert_allclose(numericals, analytical, rtol=5e-4)

#test_d2b_d2nx(ternary_basic)


@pytest.mark.sympy
@pytest.mark.parametrize("kwargs", [quaternary_basic])
def test_d3b_dnz(kwargs):
    # Rough - neeed sympy, numerical differentiation does not give any accuracy
    from sympy import symbols, diff
    zs = kwargs['zs']
    
    N = len(zs)
    b1, b2, b3, b4, n1, n2, n3, n4 = symbols('b1, b2, b3, b4, n1, n2, n3, n4')
    c1, c2, c3, c4 = symbols('c1, c2, c3, c4')
    zs_z = symbols('z1, z2, z3, z4')
    bs = [b1, b2, b3, b4]
    cs = [c1, c2, c3, c4]
    nt = n1 + n2 + n3 + n4
    ns = [n1, n2, n3, n4]
    z1 = n1/nt
    z2 = n2/nt
    z3 = n3/nt
    z4 = n4/nt
    zs_n = [z1, z2, z3, z4]

    b_n = sum([bi*zi for bi, zi in zip(bs, zs_n)])
    b_z = sum([bi*zi for bi, zi in zip(bs, zs_z)])

    c_n = sum([ci*zi for ci, zi in zip(cs, zs_n)])
    c_z = sum([ci*zi for ci, zi in zip(cs, zs_z)])

    b_n -= c_n
    b_z -= c_z

    for z in (True, False):
        diffs = {}
        for e in eos_mix_list:
            eos = e(**kwargs)
            # handle the translated volume ones
            try:
                b_subs = {bi:eos.b0s[i] for i, bi in enumerate(bs)}
            except:
                b_subs = {bi:eos.bs[i] for i, bi in enumerate(bs)}
            b_subs.update({ni: zs[i] for i, ni in enumerate(ns)})
            try:
                b_subs.update({ci: eos.cs[i] for i, ci in enumerate(cs)})
            except:
                b_subs.update({ci: 0 for ci in cs})
            
            analytical = [[[None]*N for i in range(N)] for i in range(N)]
            for i in range(N):
                for j in range(N):
                    for k in range(N):
                        if not analytical[i][j][k]:
                            if (i, j, k) in diffs:
                                t = diffs[(i, j, k)]
                            else:
                                if z:
                                    t = diff(b_z, zs_z[i], zs_z[j], zs_z[k])
                                else:
                                    t = diff(b_n, ns[i], ns[j], ns[k])
                                diffs[(i, j, k)] = t
                            v = t.subs(b_subs)
                            analytical[i][j][k] = analytical[i][k][j] = analytical[j][i][k] = analytical[j][k][i] = analytical[k][i][j] = analytical[k][j][i] = float(v)
        
        
            # Bs, deltas, epsilons
            analytical = np.array(analytical).ravel().tolist()
            if z:
                implemented = np.array(eos.d3b_dzizjzks).ravel().tolist()
            else:
                implemented = np.array(eos.d3b_dninjnks).ravel().tolist()
            assert_allclose(analytical, implemented, rtol=1e-11)

#test_d3b_dnz(quaternary_basic)


@pytest.mark.sympy
@pytest.mark.parametrize("kwargs", [quaternary_basic])
def test_d3delta_dnz(kwargs):
    from thermo.eos_mix import PRMIXTranslated
    # Rough - neeed sympy, numerical differentiation does not give any accuracy
    # Covers everything but to validate new EOSs, have to add the delta function to the list
    from sympy import symbols, diff
    zs = kwargs['zs']
    
    N = len(zs)
    b1, b2, b3, b4, n1, n2, n3, n4 = symbols('b1, b2, b3, b4, n1, n2, n3, n4')
    c1, c2, c3, c4 = symbols('c1, c2, c3, c4')
    bs = [b1, b2, b3, b4]
    cs = [c1, c2, c3, c4]
    nt = n1 + n2 + n3 + n4
    ns = [n1, n2, n3, n4]
    z1 = n1/nt
    z2 = n2/nt
    z3 = n3/nt
    z4 = n4/nt
    zs_n = [z1, z2, z3, z4]

    zs_z = symbols('z1, z2, z3, z4')

    b_n = sum([bi*zi for bi, zi in zip(bs, zs_n)])
    b_z = sum([bi*zi for bi, zi in zip(bs, zs_z)])
    c_n = sum([ci*zi for ci, zi in zip(cs, zs_n)])
    c_z = sum([ci*zi for ci, zi in zip(cs, zs_z)])
    
    for z in (True, False):
        if z:
            b_working, c_working = b_z, c_z
        else:
            b_working, c_working = b_n, c_n

        deltas = {PRMIX: 2*b_working,
                  PR78MIX: 2*b_working,
                  PRSVMIX: 2*b_working,
                  PRSV2MIX: 2*b_working,
                  TWUPRMIX: 2*b_working,
                  
                  SRKMIX: b_working,
                  APISRKMIX: b_working,
                  TWUSRKMIX: b_working,
                  
                  RKMIX: b_working,
                  IGMIX: 0,
                  VDWMIX: 0,
                  
                  PRMIXTranslated: 2*(c_working + b_working),
                  PRMIXTranslatedConsistent: 2*(c_working + b_working),
                  PRMIXTranslatedPPJP: 2*(c_working + b_working),
                 }

        for e in eos_mix_list:
            if e in deltas:
                diffs = {}
                delta = deltas[e]
            
                eos = e(**kwargs)

                to_subs = {}
                try:
                    to_subs.update({bi: eos.b0s[i] for i, bi in enumerate(bs)})
                except:
                    to_subs.update({bi: eos.bs[i] for i, bi in enumerate(bs)})
                to_subs.update({ni: zs[i] for i, ni in enumerate(ns)})
                try:
                    to_subs.update({ci: eos.cs[i] for i, ci in enumerate(cs)})
                except:
                    to_subs.update({ci: 0 for i, ci in enumerate(cs)})

                analytical = [[[None]*N for i in range(N)] for i in range(N)]
                for i in range(N):
                    for j in range(N):
                        for k in range(N):
                            if not analytical[i][j][k]:
                                if (i, j, k) in diffs:
                                    t = diffs[(i, j, k)]
                                else:
                                    if z:
                                        t = diff(delta, zs_z[i], zs_z[j], zs_z[k])
                                    else:
                                        t = diff(delta, ns[i], ns[j], ns[k])
                                    diffs[(i, j, k)] = t
                                v = t.subs(to_subs)
                                analytical[i][j][k] = analytical[i][k][j] = analytical[j][i][k] = analytical[j][k][i] = analytical[k][i][j] = analytical[k][j][i] = float(v)
            
            
                # Bs, deltas, epsilons
                analytical = np.array(analytical).ravel().tolist()
                if z:
                    implemented = np.array(eos.d3delta_dzizjzks).ravel().tolist()
                else:
                    implemented = np.array(eos.d3delta_dninjnks).ravel().tolist()
#                try:
                assert_allclose(analytical, implemented, rtol=1e-11)
#                except:
#                    print(e, delta, z)

#test_d3delta_dnz(quaternary_basic)
            
@pytest.mark.sympy
@pytest.mark.parametrize("kwargs", [quaternary_basic])
def test_d3epsilon_dnz(kwargs):
    from thermo.eos_mix import PRMIXTranslated
    # Rough - neeed sympy, numerical differentiation does not give any accuracy
    # Covers everything but to validate new EOSs, have to add the epsilon function to the list
    from sympy import symbols, diff
    zs = kwargs['zs']
    
    N = len(zs)
    b1, b2, b3, b4, n1, n2, n3, n4 = symbols('b1, b2, b3, b4, n1, n2, n3, n4')
    c1, c2, c3, c4 = symbols('c1, c2, c3, c4')
    bs = [b1, b2, b3, b4]
    cs = [c1, c2, c3, c4]
    nt = n1 + n2 + n3 + n4
    ns = [n1, n2, n3, n4]
    z1 = n1/nt
    z2 = n2/nt
    z3 = n3/nt
    z4 = n4/nt
    zs_n = [z1, z2, z3, z4]

    zs_z = symbols('z1, z2, z3, z4')

    b_n = sum([bi*zi for bi, zi in zip(bs, zs_n)])
    b_z = sum([bi*zi for bi, zi in zip(bs, zs_z)])
    c_n = sum([ci*zi for ci, zi in zip(cs, zs_n)])
    c_z = sum([ci*zi for ci, zi in zip(cs, zs_z)])
    
    for z in (True, False):
        if z:
            b_working, c_working = b_z, c_z
        else:
            b_working, c_working = b_n, c_n

        epsilons = {PRMIX: -b_working*b_working,
                  PR78MIX: -b_working*b_working,
                  PRSVMIX: -b_working*b_working,
                  PRSV2MIX: -b_working*b_working,
                  TWUPRMIX: -b_working*b_working,
                  
                  SRKMIX: 0,
                  APISRKMIX: 0,
                  TWUSRKMIX: 0,
                  
                  RKMIX: 0,
                  IGMIX: 0,
                  VDWMIX: 0,
                  
                  PRMIXTranslated: -b_working*b_working + c_working*(c_working + b_working + b_working),
                  PRMIXTranslatedConsistent: -b_working*b_working + c_working*(c_working + b_working + b_working),
                  PRMIXTranslatedPPJP: -b_working*b_working + c_working*(c_working + b_working + b_working),
                 }

        for e in eos_mix_list:
            if e in epsilons:
                diffs = {}
                epsilon = epsilons[e]
            
                eos = e(**kwargs)

                to_subs = {}
                try:
                    to_subs.update({bi: eos.b0s[i] for i, bi in enumerate(bs)})
                except:
                    to_subs.update({bi: eos.bs[i] for i, bi in enumerate(bs)})
                to_subs.update({ni: zs[i] for i, ni in enumerate(ns)})
                try:
                    to_subs.update({ci: eos.cs[i] for i, ci in enumerate(cs)})
                except:
                    to_subs.update({ci: 0 for i, ci in enumerate(cs)})

                analytical = [[[None]*N for i in range(N)] for i in range(N)]
                for i in range(N):
                    for j in range(N):
                        for k in range(N):
                            if not analytical[i][j][k]:
                                if (i, j, k) in diffs:
                                    t = diffs[(i, j, k)]
                                else:
                                    if z:
                                        t = diff(epsilon, zs_z[i], zs_z[j], zs_z[k])
                                    else:
                                        t = diff(epsilon, ns[i], ns[j], ns[k])
                                    diffs[(i, j, k)] = t
                                v = t.subs(to_subs)
                                analytical[i][j][k] = analytical[i][k][j] = analytical[j][i][k] = analytical[j][k][i] = analytical[k][i][j] = analytical[k][j][i] = float(v)
            
            
                analytical = np.array(analytical).ravel().tolist()
                if z:
                    implemented = np.array(eos.d3epsilon_dzizjzks).ravel().tolist()
                else:
                    implemented = np.array(eos.d3epsilon_dninjnks).ravel().tolist()
#                print(e)
#                try:
                assert_allclose(analytical, implemented, rtol=1e-11)
#                except:
#                    print(e)
#test_d3epsilon_dnz(quaternary_basic)

@pytest.mark.sympy
@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_d2epsilon_dnz(kwargs):
    from thermo.eos_mix import PRMIXTranslated
    from sympy import symbols, diff
    zs = kwargs['zs']
    
    N = len(zs)
    b1, b2, b3, n1, n2, n3 = symbols('b1, b2, b3, n1, n2, n3')
    c1, c2, c3 = symbols('c1, c2, c3')
    bs = [b1, b2, b3]
    cs = [c1, c2, c3]
    nt = n1 + n2 + n3 
    ns = [n1, n2, n3]
    z1 = n1/nt
    z2 = n2/nt
    z3 = n3/nt
    zs_n = [z1, z2, z3]

    zs_z = symbols('z1, z2, z3')

    b_n = sum([bi*zi for bi, zi in zip(bs, zs_n)])
    b_z = sum([bi*zi for bi, zi in zip(bs, zs_z)])
    c_n = sum([ci*zi for ci, zi in zip(cs, zs_n)])
    c_z = sum([ci*zi for ci, zi in zip(cs, zs_z)])
    
    for z in (True, False):
        if z:
            b_working, c_working = b_z, c_z
        else:
            b_working, c_working = b_n, c_n

        epsilons = {PRMIX: -b_working*b_working,
                  PR78MIX: -b_working*b_working,
                  PRSVMIX: -b_working*b_working,
                  PRSV2MIX: -b_working*b_working,
                  TWUPRMIX: -b_working*b_working,
                  
                  SRKMIX: 0,
                  APISRKMIX: 0,
                  TWUSRKMIX: 0,
                  
                  RKMIX: 0,
                  IGMIX: 0,
                  VDWMIX: 0,
                  
                  PRMIXTranslated: -b_working*b_working + c_working*(c_working + b_working + b_working),
                  PRMIXTranslatedConsistent: -b_working*b_working + c_working*(c_working + b_working + b_working),
                  PRMIXTranslatedPPJP: -b_working*b_working + c_working*(c_working + b_working + b_working),
                 }

        for e in eos_mix_list:
            if e in epsilons:
                diffs = {}
                epsilon = epsilons[e]
            
                eos = e(**kwargs)

                to_subs = {}
                try:
                    to_subs.update({bi: eos.b0s[i] for i, bi in enumerate(bs)})
                except:
                    to_subs.update({bi: eos.bs[i] for i, bi in enumerate(bs)})
                to_subs.update({ni: zs[i] for i, ni in enumerate(ns)})
                try:
                    to_subs.update({ci: eos.cs[i] for i, ci in enumerate(cs)})
                except:
                    to_subs.update({ci: 0 for i, ci in enumerate(cs)})

                analytical = [[None]*N for i in range(N)]
                for i in range(N):
                    for j in range(N):
                        if not analytical[i][j]:
                            if (i, j) in diffs:
                                t = diffs[(i, j)]
                            else:
                                if z:
                                    t = diff(epsilon, zs_z[i], zs_z[j])
                                else:
                                    t = diff(epsilon, ns[i], ns[j])
                                diffs[(i, j,)] = t
                            v = t.subs(to_subs)
                            analytical[i][j] = analytical[j][i] = float(v)
            
            
                analytical = np.array(analytical).ravel().tolist()
                if z:
                    implemented = np.array(eos.d2epsilon_dzizjs).ravel().tolist()
                else:
                    implemented = np.array(eos.d2epsilon_dninjs).ravel().tolist()
                assert_allclose(analytical, implemented, rtol=1e-11)

#test_d2epsilon_dnz(ternary_basic)


@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_ddelta_dnx(kwargs):
    kwargs = kwargs.copy()
    zs = kwargs['zs']
    del kwargs['zs'] 
    normalization = False
    
    def ddelta_dnxpartial(ni, i):
        zs_working = list(zs)
        zs_working[i] = ni
        nt = sum(zs_working)
        if normalization:
            zs_working = normalize(zs_working)
        eos = obj(zs=zs_working, **kwargs)
        return eos.delta
    
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = [derivative(ddelta_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in enumerate(zs)]
        assert_allclose(numericals, eos.ddelta_dzs)
    
    normalization = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = [derivative(ddelta_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in enumerate(zs)]
        assert_allclose(numericals, eos.ddelta_dns)
# test_ddelta_dnx(ternary_basic)

@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_d2delta_d2nx(kwargs):
    kwargs = kwargs.copy()
    zs = kwargs['zs']
    del kwargs['zs'] 
    normalization = False
    
    def d2delta_d2nxpartial(comp):
        if normalization:
            comp = normalize(comp)
        eos = obj(zs=comp, **kwargs)
        return eos.delta
    
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = hessian(d2delta_d2nxpartial, zs, perturbation=5e-5)
        analytical = eos.d2delta_dzizjs
        # For all EOEs so far, is zero
        assert_allclose(numericals, analytical, atol=1e-8)
    
    normalization = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = hessian(d2delta_d2nxpartial, zs, perturbation=5e-5)
        analytical = eos.d2delta_dninjs
        assert_allclose(numericals, analytical, rtol=1e-3)
# test_d2delta_d2nx(ternary_basic)


@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_depsilon_dnx(kwargs):
    kwargs = kwargs.copy()
    zs = kwargs['zs']
    del kwargs['zs'] 
    normalization = False
    
    def depsilon_dnxpartial(ni, i):
        zs_working = list(zs)
        zs_working[i] = ni
        nt = sum(zs_working)
        if normalization:
            zs_working = normalize(zs_working)
        eos = obj(zs=zs_working, **kwargs)
        return eos.epsilon

    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = [derivative(depsilon_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in enumerate(zs)]
        assert_allclose(numericals, eos.depsilon_dzs)

    normalization = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = [derivative(depsilon_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in enumerate(zs)]
        assert_allclose(numericals, eos.depsilon_dns)

#test_depsilon_dnx(ternary_basic)

@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_d2epsilon_d2nx(kwargs):
    kwargs = kwargs.copy()
    zs = kwargs['zs']
    del kwargs['zs'] 
    normalization = False
    
    def d2epsilon_d2nxpartial(comp):
        if normalization:
            comp = normalize(comp)
        eos = obj(zs=comp, **kwargs)
        return eos.epsilon
    
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = hessian(d2epsilon_d2nxpartial, zs, perturbation=1e-4)
        analytical = eos.d2epsilon_dzizjs
        assert_allclose(numericals, analytical, rtol=1e-6)
    
    normalization = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = hessian(d2epsilon_d2nxpartial, zs, perturbation=5e-5)
        analytical = eos.d2epsilon_dninjs
        assert_allclose(numericals, analytical, rtol=5e-4)

#test_d2epsilon_d2nx(ternary_basic)


def test_da_alpha_dnxpartial():
    liquid_IDs = ['nitrogen', 'carbon dioxide', 'H2S']
    Tcs = [126.2, 304.2, 373.2]
    Pcs = [3394387.5, 7376460.0, 8936865.0]
    omegas = [0.04, 0.2252, 0.1]
    zs = [.7, .2, .1]
    
    normalization = False
    partial_n = False

    def da_alpha_dnxpartial(ni, i):
        zs = [.7, .2, .1]
        zs[i] = ni
        nt = sum(zs)
        if normalization:
            zs = normalize(zs)
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        if partial_n:
            return eos.a_alpha*nt
        return eos.a_alpha
    
    for obj in eos_mix_list:
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        numericals = [derivative(da_alpha_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in zip((0, 1, 2), (.7, .2, .1))]
        
        assert_allclose(numericals, eos.da_alpha_dzs)

    normalization = True
    for obj in eos_mix_list:
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        numericals = [derivative(da_alpha_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in zip((0, 1, 2), (.7, .2, .1))]
        
        assert_allclose(numericals, eos.da_alpha_dns)

    partial_n = True
    for obj in eos_mix_list:
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        numericals = [derivative(da_alpha_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in zip((0, 1, 2), (.7, .2, .1))]
        assert_allclose(numericals, eos.dna_alpha_dns)


@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_d2a_alpha_d2nx(kwargs):
    kwargs = kwargs.copy()
    zs = kwargs['zs']
    del kwargs['zs'] 
    normalization = False
    
    def d2a_alpha_d2nxpartial(comp):
        if normalization:
            comp = normalize(comp)
        eos = obj(zs=comp, **kwargs)
        return eos.a_alpha
    
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = hessian(d2a_alpha_d2nxpartial, zs, perturbation=1e-4)
        analytical = eos.d2a_alpha_dzizjs
        assert_allclose(numericals, analytical, rtol=1e-6)
    
    normalization = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = hessian(d2a_alpha_d2nxpartial, zs, perturbation=5e-5)
        analytical = eos.d2a_alpha_dninjs
        assert_allclose(numericals, analytical, rtol=5e-4)

@pytest.mark.sympy
def test_d3a_alpha_dninjnk():
    from sympy import Function, symbols, diff, simplify
    a_alpha11, a_alpha12, a_alpha13, a_alpha14, a_alpha21, a_alpha22, a_alpha23, a_alpha24, a_alpha31, a_alpha32, a_alpha33, a_alpha34, a_alpha41, a_alpha42, a_alpha43, a_alpha44 = symbols(
        'a_alpha11, a_alpha12, a_alpha13, a_alpha14, a_alpha21, a_alpha22, a_alpha23, a_alpha24, a_alpha31, a_alpha32, a_alpha33, a_alpha34, a_alpha41, a_alpha42, a_alpha43, a_alpha44',
    cls=Function)
    N = 4
    T = symbols('T')
    z1, z2, z3, z4 = symbols('z1, z2, z3, z4')
    zs = [z1, z2, z3, z4]
    a_alpha_ijs = [[a_alpha11(T), a_alpha12(T), a_alpha13(T), a_alpha14(T)], [a_alpha21(T), a_alpha22(T), a_alpha23(T), a_alpha24(T)],
                   [a_alpha31(T), a_alpha32(T), a_alpha33(T), a_alpha34(T)], [a_alpha41(T), a_alpha42(T), a_alpha43(T), a_alpha44(T)]]
    a_alpha = 0
    for i in range(N):
        a_alpha_ijs_i = a_alpha_ijs[i]
        zi = zs[i]
        for j in range(i+1, N):
            term = a_alpha_ijs_i[j]*zi*zs[j]
            a_alpha += term + term
    
        a_alpha += a_alpha_ijs_i[i]*zi*zi
    
    assert 0 == diff(simplify(a_alpha), z1, z2, z3)
    
    

def test_da_alpha_dT_dnxpartial():
    liquid_IDs = ['nitrogen', 'carbon dioxide', 'H2S']
    Tcs = [126.2, 304.2, 373.2]
    Pcs = [3394387.5, 7376460.0, 8936865.0]
    omegas = [0.04, 0.2252, 0.1]
    zs = [.7, .2, .1]

    normalization = False
    partial_n = False

    def da_alpha_dT_dnxpartial(ni, i):
        zs = [.7, .2, .1]
        zs[i] = ni
        nt = sum(zs)
        if normalization:
            zs = normalize(zs)
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        if partial_n:
            return nt*eos.da_alpha_dT
        return eos.da_alpha_dT
    
    for obj in eos_mix_list:
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        numericals = [derivative(da_alpha_dT_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in zip((0, 1, 2), (.7, .2, .1))]
        assert_allclose(numericals, eos.da_alpha_dT_dzs)
        
    normalization = True
    for obj in eos_mix_list:
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        numericals = [derivative(da_alpha_dT_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in zip((0, 1, 2), (.7, .2, .1))]
        assert_allclose(numericals, eos.da_alpha_dT_dns)

    partial_n = True
    for obj in eos_mix_list:
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        numericals = [derivative(da_alpha_dT_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in zip((0, 1, 2), (.7, .2, .1))]
        assert_allclose(numericals, eos.dna_alpha_dT_dns)



def test_d2a_alpha_dT2_dnxpartial():
    liquid_IDs = ['nitrogen', 'carbon dioxide', 'H2S']
    Tcs = [126.2, 304.2, 373.2]
    Pcs = [3394387.5, 7376460.0, 8936865.0]
    omegas = [0.04, 0.2252, 0.1]
    zs = [.7, .2, .1]

    normalization = False

    def d2a_alpha_dT2_dnxpartial(ni, i):
        zs = [.7, .2, .1]
        zs[i] = ni
        nt = sum(zs)
        if normalization:
            zs = normalize(zs)
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        return eos.d2a_alpha_dT2
    
    for obj in eos_mix_list:
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        numericals = [derivative(d2a_alpha_dT2_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in zip((0, 1, 2), (.7, .2, .1))]
        assert_allclose(numericals, eos.d2a_alpha_dT2_dzs)
        
    normalization = True
    for obj in eos_mix_list:
        eos = obj(T=300, P=1e5, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        numericals = [derivative(d2a_alpha_dT2_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in zip((0, 1, 2), (.7, .2, .1))]
        assert_allclose(numericals, eos.d2a_alpha_dT2_dns)

@pytest.mark.slow
@pytest.mark.sympy
def test_d3a_alpha_dninjnks():
    from sympy import symbols, Function, diff
    
    a_alpha11, a_alpha12, a_alpha13, a_alpha14, a_alpha21, a_alpha22, a_alpha23, a_alpha24, a_alpha31, a_alpha32, a_alpha33, a_alpha34, a_alpha41, a_alpha42, a_alpha43, a_alpha44 = symbols(
        'a_alpha11, a_alpha12, a_alpha13, a_alpha14, a_alpha21, a_alpha22, a_alpha23, a_alpha24, a_alpha31, a_alpha32, a_alpha33, a_alpha34, a_alpha41, a_alpha42, a_alpha43, a_alpha44',
    cls=Function)
    N = 4
    T = symbols('T')
    n1, n2, n3, n4 = symbols('n1, n2, n3, n4')
    ns = [n1, n2, n3, n4]
    nt = n1 + n2 + n3 + n4
    z1 = n1/nt
    z2 = n2/nt
    z3 = n3/nt
    z4 = n4/nt
    zs = [z1, z2, z3, z4]
    
    a_alpha_ijs = [[a_alpha11(T), a_alpha12(T), a_alpha13(T), a_alpha14(T)], 
                   [a_alpha21(T), a_alpha22(T), a_alpha23(T), a_alpha24(T)],
                   [a_alpha31(T), a_alpha32(T), a_alpha33(T), a_alpha34(T)], 
                   [a_alpha41(T), a_alpha42(T), a_alpha43(T), a_alpha44(T)]]
    
    a_alpha = 0
    for i in range(N):
        a_alpha_ijs_i = a_alpha_ijs[i]
        zi = zs[i]
        for j in range(i+1, N):
            term = a_alpha_ijs_i[j]*zi*zs[j]
            a_alpha += term + term
        a_alpha += a_alpha_ijs_i[i]*zi*zi
        
    T, P = 170.0, 3e6
    Tcs = [126.2, 304.2, 373.2, 304.1]
    Pcs = [3394387.5, 7376460.0, 8936865.0, 7376460.0*.99]
    omegas = [0.04, 0.2252, 0.1, .06]
    eos = PRMIX(T=T, P=P, zs=[.7, .2, .02, .08], Tcs=Tcs, Pcs=Pcs, omegas=omegas, fugacities=True)
    implemented = eos.d3a_alpha_dninjnks
    
    
    diffs = {}
    a_alpha_subs = {ni: eos.zs[i] for i, ni in enumerate(ns)}
    a_alpha_subs.update({a_alpha_ijs[i][j]: eos.a_alpha_ijs[i][j] for i in eos.cmps for j in eos.cmps})
    
    N = eos.N
    analytical = [[[None]*N for i in range(N)] for i in range(N)]
    for i in range(N):
        for j in range(N):
            for k in range(N):
                if analytical[i][j][k] is None:
                    if (i, j, k) in diffs:
                        v = diffs[(i, j, k)]
                    else:
                        t = diff(a_alpha, ns[i], ns[j], ns[k])
                        v = float(t.subs(a_alpha_subs))
                        diffs[(i,j,k)] = diffs[(i,k,j)] = diffs[(j,i,k)] = diffs[(j,k,i)] = diffs[(k,i,j)] = v
                    
                    analytical[i][j][k] = analytical[i][k][j] = analytical[j][i][k] = analytical[j][k][i] = analytical[k][i][j] = analytical[k][j][i] = v
                    
    assert_allclose(implemented, analytical, rtol=1e-11)

        
@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_dH_dep_dnxpartial(kwargs):
    kwargs = kwargs.copy()
    zs = kwargs['zs']
    del kwargs['zs'] # Large test case - thought had issue but just zs did not sum to 1

    normalization = False
    partial_n = False
    
    def dH_dep_dnxpartial(ni, i):
        zs_working = list(zs)
        zs_working[i] = ni
        nt = sum(zs_working)
        if normalization:
            zs_working = normalize(zs_working)
        eos = obj(zs=zs_working, **kwargs)
        if partial_n:
            return nt*eos.H_dep_g
        return eos.H_dep_g
    
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = [derivative(dH_dep_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in enumerate(zs)]
    
        assert_allclose(numericals, eos.dH_dep_dzs(eos.Z_g, zs))
    
    normalization = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = [derivative(dH_dep_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in enumerate(zs)]
    
        assert_allclose(numericals, eos.dH_dep_dns(eos.Z_g, zs))
    
    partial_n = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = [derivative(dH_dep_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in enumerate(zs)]
    
        assert_allclose(numericals, eos.dnH_dep_dns(eos.Z_g, zs))


@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_G_dep_dnxpartial(kwargs):
    kwargs = kwargs.copy()
    zs = kwargs['zs']
    del kwargs['zs'] 
    normalization = False
    partial_n = False
    def G_dep_dnxpartial(comp):
        nt = sum(comp)
        if normalization:
            comp = normalize(comp)
        eos = obj(zs=comp, **kwargs)
        if partial_n:
            return nt*eos.G_dep_g
        return eos.G_dep_g
    
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = jacobian(G_dep_dnxpartial, zs, perturbation=1e-7)
        analytical = eos.dG_dep_dzs(eos.Z_g, zs)
        assert_allclose(numericals, analytical, rtol=5e-7)
    
    normalization = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = jacobian(G_dep_dnxpartial, zs, perturbation=5e-7)
        analytical = eos.dG_dep_dns(eos.Z_g, zs)
        assert_allclose(numericals, analytical, rtol=1e-5)

    partial_n = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = jacobian(G_dep_dnxpartial, zs, perturbation=5e-7)
        analytical = eos.dnG_dep_dns(eos.Z_g, zs)
        assert_allclose(numericals, analytical, rtol=1e-5)


@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_dG_dep_d2nx(kwargs):
    kwargs = kwargs.copy()
    zs = kwargs['zs']
    del kwargs['zs'] 
    normalization = False

    def G_dep_d2nxpartial(comp):
        if normalization:
            comp = normalize(comp)
        eos = obj(zs=comp, **kwargs)
        return eos.G_dep_g
    
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = hessian(G_dep_d2nxpartial, zs, perturbation=2e-4)
        analytical = eos.d2G_dep_dzizjs(eos.Z_g, zs)
        assert_allclose(numericals, analytical, rtol=5e-5)
    
    normalization = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = hessian(G_dep_d2nxpartial, zs, perturbation=2e-4)
        analytical = eos.d2G_dep_dninjs(eos.Z_g, zs)
        assert_allclose(numericals, analytical, rtol=5e-4)



@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_lnphi_dnx(kwargs):
    kwargs = kwargs.copy()
    zs = kwargs['zs']
    del kwargs['zs'] 
    normalization = False
    partial_n = False
    def lnphi_dnxpartial(comp):
        nt = sum(comp)
        if normalization:
            comp = normalize(comp)
        eos = obj(zs=comp, **kwargs)
        return log(eos.phi_g)
    
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = jacobian(lnphi_dnxpartial, zs, perturbation=1e-7)
        analytical = eos.dlnphi_dzs(eos.Z_g, zs)
        assert_allclose(numericals, analytical, rtol=5e-7)
    
    normalization = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = jacobian(lnphi_dnxpartial, zs, perturbation=5e-7)
        analytical = eos.dlnphi_dns(eos.Z_g, zs)
        assert_allclose(numericals, analytical, rtol=1e-6)

@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_dlnphi_d2nx(kwargs):
    kwargs = kwargs.copy()
    zs = kwargs['zs']
    del kwargs['zs'] 
    normalization = False

    def lnphi_d2nxpartial(comp):
        if normalization:
            comp = normalize(comp)
        eos = obj(zs=comp, **kwargs)
        return log(eos.phi_g)
    
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = hessian(lnphi_d2nxpartial, zs, perturbation=2e-4)
        analytical = eos.d2lnphi_dzizjs(eos.Z_g, zs)
        assert_allclose(numericals, analytical, rtol=5e-5)
    
    normalization = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = hessian(lnphi_d2nxpartial, zs, perturbation=2e-4)
        analytical = eos.d2lnphi_dninjs(eos.Z_g, zs)
        assert_allclose(numericals, analytical, rtol=5e-4)
        

@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_dV_dnxpartial(kwargs):
    kwargs = kwargs.copy()
    zs = kwargs['zs']
    del kwargs['zs'] 

    normalization = False
    partial_n = False
    
    def dV_dnxpartial(ni, i):
        zs_working = list(zs)
        zs_working[i] = ni
        nt = sum(zs_working)
        if normalization:
            zs_working = normalize(zs_working)
        eos = obj(zs=zs_working, **kwargs)
        if partial_n:
            return nt*eos.V_g
        return eos.V_g
    
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = [derivative(dV_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in enumerate(zs)]
        assert_allclose(numericals, eos.dV_dzs(eos.Z_g, zs), atol=1e-16)
    
    normalization = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = [derivative(dV_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in enumerate(zs)]
        assert_allclose(numericals, eos.dV_dns(eos.Z_g, zs), atol=1e-16)
    
    partial_n = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = [derivative(dV_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in enumerate(zs)]
        assert_allclose(numericals, eos.dnV_dns(eos.Z_g, zs))


@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_V_d2nx(kwargs):
    kwargs = kwargs.copy()
    zs = kwargs['zs']
    del kwargs['zs'] 
    normalization = False
    
    def V_d2nxpartial(comp):
        if normalization:
            comp = normalize(comp)
        eos = obj(zs=comp, **kwargs)
        return eos.V_g
    
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = hessian(V_d2nxpartial, zs, perturbation=1e-4)
        analytical = eos.d2V_dzizjs(eos.Z_g, zs)
        assert_allclose(numericals, analytical, rtol=5e-5)
    
    normalization = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = hessian(V_d2nxpartial, zs, perturbation=5e-5)
        analytical = eos.d2V_dninjs(eos.Z_g, zs)
        assert_allclose(numericals, analytical, rtol=5e-4)


@pytest.mark.parametrize("kwargs", [ternary_basic])
def test_dZ_dnxpartial(kwargs):
    kwargs = kwargs.copy()
    zs = kwargs['zs']
    del kwargs['zs'] 

    normalization = False
    partial_n = False
    
    def dZ_dnxpartial(ni, i):
        zs_working = list(zs)
        zs_working[i] = ni
        nt = sum(zs_working)
        if normalization:
            zs_working = normalize(zs_working)
        eos = obj(zs=zs_working, **kwargs)
        if partial_n:
            return nt*eos.Z_g
        return eos.Z_g
    
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = [derivative(dZ_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in enumerate(zs)]
        assert_allclose(numericals, eos.dZ_dzs(eos.Z_g, zs), atol=1e-13)
    
    normalization = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = [derivative(dZ_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in enumerate(zs)]
        assert_allclose(numericals, eos.dZ_dns(eos.Z_g, zs), atol=1e-13)
    
    partial_n = True
    for obj in eos_mix_list:
        eos = obj(zs=zs, **kwargs)
        numericals = [derivative(dZ_dnxpartial, ni, dx=1e-3, order=7, args=(i,)) 
            for i, ni in enumerate(zs)]
        assert_allclose(numericals, eos.dnZ_dns(eos.Z_g, zs))


quaternary_dthermodynamics = dict(T=300.0, P=1e5, Tcs=[126.2, 304.2, 373.2, 304.1], 
                        Pcs=[3394387.5, 7376460.0, 8936865.0, 7376460.0*.99],
                        omegas=[0.04, 0.2252, 0.1, .06],
                        zs=[.7, .2, .02, .08])


@pytest.mark.parametrize("kwargs,T,P,zs", [[quaternary_dthermodynamics, 170.0, 3e6, [.7, .2, .02, .08]]])
def test_dthermodynamics_dnxpartial(kwargs, T, P, zs):
    # test_dthermodynamics_dnxpartial(quaternary_dthermodynamics, 170.0, 3e6, [.7, .2, .02, .08])
    kwargs = kwargs.copy()
    del kwargs['zs']
    del kwargs['T']
    del kwargs['P']

    attr_pures =   ['dP_dT',  'dP_dV',  'dV_dT',  'dV_dP',  'dT_dV',  'dT_dP',  'd2P_dT2', 'd2P_dV2', 'd2V_dT2', 'd2V_dP2', 'd2T_dV2', 'd2T_dP2', 'd2V_dPdT', 'd2P_dTdV', 'd2T_dPdV', 'H_dep',   'S_dep',  'V_dep',    'U_dep',   'G_dep',   'A_dep']
    attr_derivs =  ['d2P_dT', 'd2P_dV', 'd2V_dT', 'd2V_dP', 'd2T_dV', 'd2T_dP', 'd3P_dT2', 'd3P_dV2', 'd3V_dT2', 'd3V_dP2', 'd3T_dV2', 'd3T_dP2', 'd3V_dPdT', 'd3P_dTdV', 'd3T_dPdV', 'dH_dep_', 'dS_dep_', 'dV_dep_', 'dU_dep_', 'dG_dep_', 'dA_dep_']

    eos_mix_working = [SRKMIX, APISRKMIX, PRMIX, PR78MIX, PRSVMIX, PRSV2MIX, TWUPRMIX]
    
    def dthing_dnxpartial(ni, i):
        zs_working = list(zs)
        zs_working[i] = ni
        nt = sum(zs_working)
        if normalization:
            zs_working = normalize(zs_working)
        eos = obj(zs=zs_working, T=T, P=P, **kwargs)
        return getattr(eos, attr_pure_phase)
    
    for attr_pure, attr_der in zip(attr_pures, attr_derivs):
        for phase in ['l', 'g']:
            attr_pure_phase = attr_pure + '_' + phase
            attr_der_phase = attr_der + 'dzs_%s' %phase
            
            normalization = False
            for obj in eos_mix_working:
                eos = obj(zs=zs, T=T, P=P, **kwargs)
                eos.set_dnzs_derivatives_and_departures()
                numericals = [derivative(dthing_dnxpartial, ni, dx=1e-4, order=7, args=(i,)) 
                    for i, ni in enumerate(zs)]
                assert_allclose(numericals, getattr(eos, attr_der_phase))
            
            normalization = True
            attr_der_phase = attr_der + 'dns_%s' %phase
            for obj in eos_mix_working:
                eos = obj(zs=zs, T=T, P=P, **kwargs)
                eos.set_dnzs_derivatives_and_departures()
                numericals = [derivative(dthing_dnxpartial, ni, dx=1e-4, order=7, args=(i,)) 
                    for i, ni in enumerate(zs)]
                assert_allclose(numericals, getattr(eos, attr_der_phase))
                    
def test_fugacities_numerical_all_eos_mix():
    liquid_IDs = ['nitrogen', 'carbon dioxide', 'H2S']
    Tcs = [126.2, 304.2, 373.2]
    Pcs = [3394387.5, 7376460.0, 8936865.0]
    omegas = [0.04, 0.2252, 0.1]
    zs = [.7, .2, .1]
    P = 1e5

    def to_diff(ni, i):
        zs = [.7, .2, .1]
        zs[i] = ni
        nt = sum(zs)
        zs = normalize(zs)
        eos = obj(T=300, P=P, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        return log(eos.fugacity_g)*nt
    
    for obj in eos_mix_list:
        eos = obj(T=300, P=P, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        numericals = [exp(derivative(to_diff, ni, dx=1e-3, order=7, args=(i,))) 
            for i, ni in zip((0, 1, 2), (.7, .2, .1))]
        
        analytical = [P*i for i in eos.phis_g]
        assert_allclose(numericals, analytical)
        
        analytical_2 = [exp(i)*P for i in GCEOSMIX.fugacity_coefficients(eos, eos.Z_g, zs)]
        assert_allclose(numericals, analytical_2)
# test_fugacities_numerical_all_eos_mix()

def test_dlnphis_dT_vs_Hdep_identity():
    liquid_IDs = ['nitrogen', 'carbon dioxide', 'H2S']
    Tcs = [126.2, 304.2, 373.2]
    Pcs = [3394387.5, 7376460.0, 8936865.0]
    omegas = [0.04, 0.2252, 0.1]
    zs = [.7, .2, .1]
    P = 1e5
    T = 300.0
    
    for obj in eos_mix_list:
        eos = obj(T=300, P=P, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
        dlnphis_dT = eos.dlnphis_dT('g')
        numerical = sum(zi*di for zi, di in zip(zs, dlnphis_dT))
        # In Michelsen
        analytical = -eos.H_dep_g/(R*T*T)
    
        assert_allclose(numerical, analytical)




'''
from sympy import *
a_alpha11, a_alpha12, a_alpha13, a_alpha14, a_alpha21, a_alpha22, a_alpha23, a_alpha24, a_alpha31, a_alpha32, a_alpha33, a_alpha34, a_alpha41, a_alpha42, a_alpha43, a_alpha44 = symbols(
    'a_alpha11, a_alpha12, a_alpha13, a_alpha14, a_alpha21, a_alpha22, a_alpha23, a_alpha24, a_alpha31, a_alpha32, a_alpha33, a_alpha34, a_alpha41, a_alpha42, a_alpha43, a_alpha44')
N = 4
n1, n2, n3, n4 = symbols('n1, n2, n3, n4')
ns = [n1, n2, n3, n4]
nt = n1 + n2 + n3 + n4
z1 = n1/nt
z2 = n2/nt
z3 = n3/nt
z4 = n4/nt

zs = [z1, z2, z3, z4]

a_alpha_ijs = [[a_alpha11, a_alpha12, a_alpha13, a_alpha14], [a_alpha21, a_alpha22, a_alpha23, a_alpha24],
               [a_alpha31, a_alpha32, a_alpha33, a_alpha34], [a_alpha41, a_alpha42, a_alpha43, a_alpha44]]        
a_alpha = 0
for i in range(N):
    a_alpha_ijs_i = a_alpha_ijs[i]
    zi = zs[i]
    for j in range(i+1, N):
        term = a_alpha_ijs_i[j]*zi*zs[j]
        a_alpha += term + term

    a_alpha += a_alpha_ijs_i[i]*zi*zi

simplify(diff(a_alpha, n2))
# Top large term is actually a_alpha, so the expression simplifies quite a lot
'''




def test_d2A_dep_dninjs():
    # ['nitrogen', 'methane', 'ethane']
    zs = [.1, .7, .2]

    T, P = 223.33854381006378, 7222576.081635592
    Tcs, Pcs, omegas = [126.2, 190.56400000000002, 305.32], [3394387.5, 4599000.0, 4872000.0], [0.04, 0.008, 0.098]
    e = SRKMIX
    eos = e(T=T, P=P, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)

    def to_hess(zs):
        zs = normalize(zs)
        return e(T=T, P=P, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas).A_dep_l
    
    d2A_dep_dninjs_expect = [[-13470.857294626958, -3088.1224994370855, 18357.465856316656],
     [-3088.1224994370873, -773.2826253845835, 4208.830036112632],
     [18357.46585631667, 4208.830036112632, -24170.42087645741]]
    
    d2A_dep_dninjs_numerical = hessian(to_hess, zs, perturbation=3e-5)
    d2A_dep_dninjs_analytical = eos.d2A_dep_dninjs(eos.Z_l, zs)
    assert_allclose(d2A_dep_dninjs_expect, d2A_dep_dninjs_analytical, rtol=1e-12)
    
    assert_allclose(d2A_dep_dninjs_numerical, d2A_dep_dninjs_analytical, rtol=1.5e-4)
    
    
    
def test_dP_dns_Vt():    
    liquid_IDs = ['nitrogen', 'carbon dioxide', 'H2S', 'methane']
    zs = [0.1, 0.2, 0.3, 0.4]
    Tcs = [126.2, 304.2, 373.2, 190.5640]
    Pcs = [3394387.5, 7376460.0, 8936865.0, 4599000.0]
    omegas = [0.04, 0.2252, 0.1, 0.008]
    
    T = 300.0
    eos = PRMIX(T=T, P=1e6, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
    Vt = eos.V_g # 0.0023950572174592445
    
    
    def diff_for_dP_dn(ns):
        V = Vt/sum(ns)
        zs = normalize(ns)
        return PRMIX(T=T, V=V, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas).P
    
    # dP_dns_Vt
    dP_dns_Vt_expect = [1008852.4623272286, 945656.6443815783, 925399.0474464404, 980456.0528080815]
    dP_dns_Vt_analytical = eos.dP_dns_Vt('g')
    assert_allclose(dP_dns_Vt_expect, dP_dns_Vt_analytical, rtol=1e-12)
    
    dP_dns_Vt_numerical = jacobian(diff_for_dP_dn, zs, perturbation=1e-7)
    assert_allclose(dP_dns_Vt_analytical, dP_dns_Vt_numerical, rtol=1e-8)


    # d2P_dninjs_Vt
    d2P_dninjs_Vt_expect = [[-5788.200297491028, -37211.91404188248, -47410.861447428724, -19515.839351858624],
                            [-37211.91404188248, -107480.51179668301, -130009.03722609379, -68774.79519256642],
                            [-47410.861447429175, -130009.03722609379, -156450.94968107349, -84635.02057801858],
                            [-19515.839351858624, -68774.79519256689, -84635.02057801858, -41431.49651609236]]
    
    d2P_dninjs_Vt_analytical = eos.d2P_dninjs_Vt('g')
    assert_allclose(d2P_dninjs_Vt_expect, d2P_dninjs_Vt_analytical, rtol=1e-12)
    
    def diff_for_dP_dn(ns):
        V = Vt/sum(ns)
        zs = normalize(ns)
        return PRMIX(T=T, V=V, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas).P
    d2P_dninjs_Vt_numerical = hessian(diff_for_dP_dn, zs, perturbation=1.5e-4)
    assert_allclose(d2P_dninjs_Vt_numerical, d2P_dninjs_Vt_analytical, rtol=2e-4)
    
    
    
def test_lnphis_basic():
    # Not 100% positive these are correct. But to 4.8 nines with jacobian, it's a match.
    # There is no bias about which direction a number is wrong though.
    liquid_IDs = ['nitrogen', 'carbon dioxide', 'H2S', 'methane']
    zs = [0.1, 0.2, 0.3, 0.4]
    Tcs = [126.2, 304.2, 373.2, 190.5640]
    Pcs = [3394387.5, 7376460.0, 8936865.0, 4599000.0]
    omegas = [0.04, 0.2252, 0.1, 0.008]
    
    T, P = 300, 1e6
    eos = PRMIX(T=T, P=P, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
    
    def lnphis_dn(ns):
        zs = normalize(ns)
        return PRMIX(T=T, P=P, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas).lnphis_g
    
    dlnphis_dns_numerical = jacobian(lnphis_dn, zs, perturbation=1e-7, scalar=False)
    dlnphis_dns_analytical = eos.dlnphis_dns(eos.Z_g, zs)
    dlnphis_dns_expect = [[-0.02537902325861477, 0.007204512789763549, 0.0175466983422222, -0.01041859661225469],
                          [0.007204833259016413, -0.0020454514833986304, -0.004981543870380252, 0.0029576619027266195],
                          [0.017546853751371598, -0.0049815999187692375, -0.012132256778313248, 0.007203147082507459], 
                          [-0.01041793395202692, 0.002957664659691675, 0.0072031571097258065, -0.004276674933823978]]
    assert_allclose(dlnphis_dns_analytical, dlnphis_dns_expect, rtol=1e-12)
    assert_allclose(dlnphis_dns_analytical, dlnphis_dns_numerical, rtol=8e-5)


def test_IGMIX():
    T = 270.0
    P = 76E5
    zs = [0.3, 0.1, 0.6]
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    eos = IGMIX(T=T, P=P, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
    
    assert_allclose(eos.fugacities_g, [2280000.0, 760000.0, 4560000.0], rtol=1e-14)
    assert_allclose(eos.H_dep_g, 0)
    assert_allclose(eos.S_dep_g, 0)
    
def test_PRMIX_composition_derivatives_ternary(): 
    
    T = 270.0
    P = 76E5
    zs = [0.3, 0.1, 0.6]
    Tcs = [126.2, 190.6, 305.4]
    Pcs = [33.9E5, 46.0E5, 48.8E5]
    omegas = [0.04, 0.008, 0.098]
    kijs = [[0, 0.038, 0.08], [0.038, 0, 0.021], [0.08, 0.021, 0]]
    eos = PRMIX(T=T, P=P, zs=zs, Tcs=Tcs, Pcs=Pcs, omegas=omegas)
    
    db_dzs_expect = [2.4079724954895717e-05, 2.6801366023576428e-05, 4.0480053330897585e-05]
    assert_allclose(eos.db_dzs, db_dzs_expect, rtol=1e-12)
    db_dns_expect = [-1.0112361132469188e-05, -7.390720063788477e-06, 6.28796724353268e-06]
    assert_allclose(eos.db_dns, db_dns_expect, rtol=1e-12)
    dnb_dns_expect = [2.4079724954895717e-05, 2.6801366023576428e-05, 4.0480053330897585e-05]
    assert_allclose(eos.dnb_dns, dnb_dns_expect, rtol=1e-12)
    
    d2b_dzizjs_expect = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    assert_allclose(eos.d2b_dzizjs, d2b_dzizjs_expect, atol=1e-12)
    
    d2b_dninjs_expect = [[2.022472226493838e-05, 1.750308119625767e-05, 3.824393888936512e-06],
     [1.7503081196257666e-05, 1.4781440127576955e-05, 1.1027528202557974e-06],
     [3.8243938889365085e-06, 1.1027528202557974e-06, -1.257593448706536e-05]]
    assert_allclose(eos.d2b_dninjs, d2b_dninjs_expect, rtol=1e-12)
    
    d3b_dzizjzks_expect = [[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
     [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
     [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]]
    assert_allclose(eos.d3b_dzizjzks, d3b_dzizjzks_expect, atol=1e-12)
    
    d3b_dninjnks_expect = [[[-6.067416679481513e-05, -5.523088465745371e-05, -2.7873510042811394e-05],
      [-5.52308846574537e-05, -4.978760252009228e-05, -2.2430227905449965e-05],
      [-2.7873510042811387e-05, -2.2430227905449965e-05, 4.92714670919235e-06]],
     [[-5.52308846574537e-05, -4.978760252009228e-05, -2.2430227905449965e-05],
      [-4.978760252009227e-05, -4.434432038273085e-05, -1.6986945768088536e-05],
      [-2.2430227905449958e-05, -1.6986945768088536e-05, 1.0370428846553779e-05]],
     [[-2.78735100428114e-05, -2.243022790544998e-05, 4.927146709192336e-06],
      [-2.2430227905449972e-05, -1.698694576808855e-05, 1.0370428846553765e-05],
      [4.927146709192343e-06, 1.0370428846553765e-05, 3.772780346119608e-05]]]
    assert_allclose(eos.d3b_dninjnks, d3b_dninjnks_expect, rtol=1e-12)
    
    da_alpha_dzs_expect = [0.3811648055400453, 0.5734845502198427, 0.9931275290717199]
    assert_allclose(eos.da_alpha_dzs, da_alpha_dzs_expect, rtol=1e-12)
    
    da_alpha_dns_expect = [-0.3864096085869845, -0.19408986390718708, 0.2255531149446901]
    assert_allclose(da_alpha_dns_expect, eos.da_alpha_dns, rtol=1e-12)
    
    dna_alpha_dns_expect = [-0.0026224015234695974, 0.1896973431563278, 0.609340322008205]
    assert_allclose(dna_alpha_dns_expect, dna_alpha_dns_expect, rtol=1e-12)
    
    d2a_alpha_dzizjs_expect = [[0.1892801613868494, 0.284782977443788, 0.4931707656326862],
     [0.284782977443788, 0.42847250154227606, 0.7420040113874646],
     [0.4931707656326862, 0.7420040113874646, 1.2849598304052794]]
    assert_allclose(eos.d2a_alpha_dzizjs, d2a_alpha_dzizjs_expect, rtol=1e-12)
    
    d2a_alpha_dninjs_expect = [[0.9673441816077575, 0.6782075083051011, 0.047309338790245015],
     [0.6782075083051011, 0.43725754304399445, -0.08849690481457184],
     [0.047309338790245015, -0.08849690481457184, -0.3848270435005108]]
    assert_allclose(eos.d2a_alpha_dninjs, d2a_alpha_dninjs_expect, rtol=1e-12)
    
    d3a_alpha_dzizjzks_expect = [[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
     [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
     [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]]
    assert_allclose(eos.d3a_alpha_dzizjzks, d3a_alpha_dzizjzks_expect, rtol=1e-12)
    
    d3a_alpha_dninjnks_expect = [[[-3.4856074381246387, -2.7137002342736096, -1.0293935139179382],
      [-2.713700234273608, -2.0381664465056772, -0.5641471694625864],
      [-1.0293935139179382, -0.5641471694625864, 0.45102348923524893]],
     [[-2.713700234273608, -2.0381664465056772, -0.5641471694625864],
      [-2.0381664465056772, -1.459006074820845, -0.19527424109033475],
      [-0.5641471694625864, -0.19527424109033298, 0.6096089742949236]],
     [[-1.0293935139179382, -0.5641471694625864, 0.45102348923524893],
      [-0.5641471694625864, -0.19527424109033298, 0.6096089742949218],
      [0.45102348923524893, 0.6096089742949218, 0.955643571334928]]]
    assert_allclose(eos.d3a_alpha_dninjnks, d3a_alpha_dninjnks_expect, rtol=1e-12)
    
    da_alpha_dT_dzs_expect = [-0.0009353409194855748, -0.001087066965623279, -0.0018455010841509755]
    assert_allclose(eos.da_alpha_dT_dzs, da_alpha_dT_dzs_expect, rtol=1e-12)
    
    da_alpha_dT_dns_expect = [0.0005612687034130106, 0.0004095426572753064, -0.00034889146125239006]
    assert_allclose(eos.da_alpha_dT_dns, da_alpha_dT_dns_expect, rtol=1e-12)
    
    dna_alpha_dT_dns_expect = [-0.00018703610803628209, -0.00033876215417398634, -0.0010971962727016828]
    assert_allclose(eos.dna_alpha_dT_dns, dna_alpha_dT_dns_expect, rtol=1e-12)
    
    d2a_alpha_dT2_dzs_expect = [2.831297854045874e-06, 3.042536571840166e-06, 5.128157024727633e-06]
    assert_allclose(eos.d2a_alpha_dT2_dzs, d2a_alpha_dT2_dzs_expect, rtol=1e-12)
    
    d2a_alpha_dT2_dns_expect = [-1.3992393741884843e-06, -1.1880006563941923e-06, 8.976197964932746e-07]
    assert_allclose(eos.d2a_alpha_dT2_dns, d2a_alpha_dT2_dns_expect, rtol=1e-12)
    
    
def test_dlnphis_dns():
    eos = PRMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.6, 0.4], kijs=[[0,0],[0,0]])
    eos.dlnphis_dns(eos.Z_g, eos.zs)
    
    assert_allclose(eos.dfugacities_dns('g'), [[337128.52253434795, -505700.6314376668],
                     [-280166.2742094089, 420239.6290278874]], rtol=1e-5)
         

@pytest.mark.mpmath
def test_volume_issues():
    e = PRMIX(Tcs=[611.7], Pcs=[2110000.0], omegas=[0.49], kijs=[[0.0]], 
          zs=[1], T=0.11233240329780202, P=0.012328467394420634)
    assert_allclose(e.V_l, float(e.V_l_mpmath), rtol=1e-14)
    
    obj = PRMIX(Tcs=[611.7], Pcs=[2110000.0], omegas=[0.49], kijs=[[0.0]],  zs=[1],
                T=0.11233240329780202, P=0.012328467394420634)
    assert_allclose(obj.sorted_volumes, obj.mpmath_volumes_float, rtol=1e-14)
    
    obj = PRMIX(Tcs=[611.7], Pcs=[2110000.0], omegas=[0.49], kijs=[[0.0]], zs=[1],
          T=0.11233240329780202, P=0.012328467394420634)
    assert_allclose(obj.sorted_volumes, obj.mpmath_volumes_float, rtol=1e-14)
    
    
    obj = PRMIX(Tcs=[611.7], Pcs=[2110000.0], omegas=[0.49], kijs=[[0.0]], zs=[1],
                T=.01, P=1e9)
    assert_allclose(obj.sorted_volumes, obj.mpmath_volumes_float, rtol=1e-14)
    
    obj = PRMIX(Tcs=[611.7], Pcs=[2110000.0], omegas=[0.49], kijs=[[0.0]], zs=[1],
                T=1e-4, P=1e8)
    assert_allclose(obj.sorted_volumes, obj.mpmath_volumes_float, rtol=1e-14)
    
    obj = SRKMIX(Tcs=[647.14], Pcs=[22048320.0], omegas=[0.344], kijs=[[0]], zs=[1], T=708, P=.097)
    assert_allclose(obj.sorted_volumes, obj.mpmath_volumes_float, rtol=1e-14)
    
    obj = SRKMIX(Tcs=[647.14], Pcs=[22048320.0], omegas=[0.344], kijs=[[0]],
                 zs=[1], T=1010, P=.1)
    assert_allclose(obj.sorted_volumes, obj.mpmath_volumes_float, rtol=1e-14)
    
    
    obj = SRKMIX(Tcs=[647.14], Pcs=[22048320.0], omegas=[0.344], kijs=[[0]],
                 zs=[1], T=100, P=10)
    assert_allclose(obj.sorted_volumes, obj.mpmath_volumes_float, rtol=1e-14)
    
    obj = SRKMIX(Tcs=[647.14], Pcs=[22048320.0], omegas=[0.344], kijs=[[0]],
                 zs=[1], T=400, P=1.5e5)
    assert_allclose(obj.sorted_volumes, obj.mpmath_volumes_float, rtol=1e-14)
    
    obj = PRMIX(Tcs=[126.2], Pcs=[3394387.5], omegas=[0.04], kijs=[[0.0]], zs=[1],
                T=.01149756995397728, P=.01)
    assert_allclose(obj.sorted_volumes, obj.mpmath_volumes_float, rtol=1e-14)
    
    obj = PRMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[ 0.04, 0.011], 
                zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    
    assert_allclose(obj.sorted_volumes, obj.mpmath_volumes_float, rtol=1e-14)
    
    
    # TV iteration - check back calculation works to the exact precision now
    obj = PR(Tc=507.6, Pc=3025000, omega=0.2975, T=5., P=1E-4)
    TV = PR(Tc=507.6, Pc=3025000, omega=0.2975, T=5., V=obj.V_l_mpmath)
    assert_allclose(obj.P, TV.P, rtol=1e-12)
    TV = PR(Tc=507.6, Pc=3025000, omega=0.2975, T=5., V=obj.V_g_mpmath)
    assert_allclose(obj.P, TV.P, rtol=1e-12)

    # Case where floating point NR iteration behaves horribly, but one of the methods
    # still gets a pretty small max rel error (although it seems dumb)
    obj = SRKMIX(Tcs=[405.6], Pcs=[11277472.5], omegas=[0.25], kijs=[[0]], zs=[1], T=0.04229242874389471, P=0.02782559402207126)
    assert obj.volume_error() < 1e-12
    
    # Case where NR switches which root is converged to
    obj = PR78MIX(Tcs=[647.14], Pcs=[22048320.0], omegas=[0.344], kijs=[[0]], zs=[1], T=494.1713361323858, P=0.13257113655901095)
    assert obj.volume_error() < 1e-12
    
    # Case where NR low P is used
    obj = RK(Tc=768.0, Pc=1070000.0, omega=0.8805, T=0.000954095, P=0.0790604)
    assert obj.volume_error() < 1e-12
    
def test_PV_issues_multiple_solutions_T():
    obj = APISRKMIX(Tcs=[768.0], Pcs=[1070000.0], omegas=[0.8805], zs=[1], V=0.0026896181445057303, P=14954954.954954954, only_g=True)
    assert_allclose(obj.T, 1e4)
    obj = APISRKMIX(Tcs=[768.0], Pcs=[1070000.0], omegas=[0.8805], zs=[1], V=0.0026896181445057303, P=14954954.954954954, only_l=True)
    assert_allclose(obj.T, 6741.680441295266)

def test_to_TPV_pure():
    # PRSV2MIX
    eos = PRSV2MIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., P=1E6, 
                   kappa1s=[0.05104], kappa2s=[0.8634], kappa3s=[0.460])
    eos2 = eos.to_TPV_pure(T=eos.T, P=eos.P, V=None, i=0)
    assert_allclose(eos.V_l, eos2.V_l, rtol=1e-13)

    # PRSVMIX
    eos = PRSVMIX(Tcs=[507.6], Pcs=[3025000], omegas=[0.2975], zs=[1], T=299., P=1E6, kappa1s=[0.05104])
    eos2 = eos.to_TPV_pure(T=eos.T, P=eos.P, V=None, i=0)
    assert_allclose(eos.V_l, eos2.V_l, rtol=1e-13)    

    # APISRKMIX
    eos = APISRKMIX(Tcs=[514.0], Pcs=[6137000.0], omegas=[0.635], S1s=[1.678665], S2s=[-0.216396], zs=[1], T=299., P=1E6)
    eos2 = eos.to_TPV_pure(T=eos.T, P=eos.P, V=None, i=0)
    assert_allclose(eos.V_l, eos2.V_l, rtol=1e-13)
    
    # RKMIX
    eos = RKMIX(T=115, P=1E6, Tcs=[126.1], Pcs=[33.94E5], omegas=[0.04], zs=[1.0])
    eos2 = eos.to_TPV_pure(T=eos.T, P=eos.P, V=None, i=0)
    assert_allclose(eos.V_l, eos2.V_l, rtol=1e-13)
    
    # Check that the set of EOSs are covered.
    covered_here = [PRSVMIX, PRSV2MIX, APISRKMIX, RKMIX]
    covered_all = eos_mix_no_coeffs_list + covered_here
    assert set(covered_all) == set(eos_mix_list)
    


@pytest.mark.mpmath
def test_volume_issues_low_P():
    # Low pressure  section
    eos = PRMIX(T=115, P=1E6, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert eos.to(T=0.0004498432668969453, P=2.3299518105153813e-20, zs=eos.zs).volume_error() < 1e-12
    
    assert eos.to(T=0.00021209508879201926, P=3.5564803062232667e-11, zs=eos.zs).volume_error() < 1e-12
    assert eos.to(T=7.906043210907728, P=7.543120063354915e-15, zs=eos.zs).volume_error() < 1e-12
    assert eos.to(T=206.9138081114788, P=1.4384498882876541e-05, zs=eos.zs).volume_error() < 1e-12

    assert eos.to(T=1e-6, P=2.3299518105153813e-20, zs=eos.zs).volume_error() < 1e-12
        
    eos = PR(Tc=190.564, Pc=4599000.0, omega=0.008, T=0.00014563484775, P=2.81176869797e-06)
    assert eos.volume_error() < 1e-12

    eos = PR(Tc=190.56400000000002, Pc=4599000.0, omega=0.008, T=0.00014563484775, P=2.81176869797e-150)
    assert eos.volume_error() < 1e-12

    eos = TWUSRKMIX(T=1e-4, P=1e-200, Tcs=[126.1, 190.6], Pcs=[33.94E5, 46.04E5], omegas=[0.04, 0.011], zs=[0.5, 0.5], kijs=[[0,0],[0,0]])
    assert eos.volume_error() < 1e-12
    eos = PRSV(Tc=507.6, Pc=3025000, omega=0.2975, T=0.013257113655901155, P=0.00033932217718954545, kappa1=0.05104)
    assert eos.volume_error() < 1e-12


def test_solve_T_issues():
    obj = SRKMIX(Tcs=[611.7], Pcs=[2110000.0], omegas=[0.49], kijs=[[0]], zs=[1], V=0.00042281487181772243, P=247707635.59916735)
    assert_allclose(obj.T, 10000, rtol=1e-9)

    # Initial liquid guess was leading to bad answers
    obj = SRKMIX(Tcs=[611.7], Pcs=[2110000.0], omegas=[0.49], kijs=[[0]], zs=[1], T=636.8250, P=7934096.6658)
    assert_allclose(obj.to(zs=[1], V=obj.V_l, P=obj.P).T, obj.T, rtol=1e-7)  
    
    obj = SRKMIX(Tcs=[5.1889], Pcs=[226968.0], omegas=[-0.387], kijs=[[0]], zs=[1], T=1.0405, P=6.9956)
    assert_allclose(obj.to(zs=[1], V=obj.V_l, P=obj.P).T, obj.T, rtol=1e-7)
    
    # High and low solution at crazy T
    kwargs = dict(Tcs=[768.0], Pcs=[1070000.0], omegas=[0.8805], S1s=[1.7303161495675], S2s=[0.0], zs=[1], P=359381366.3805, V=0.0006354909990692889)
    assert_allclose(APISRKMIX(**kwargs).T, 7220.8089999999975)
    assert_allclose(APISRKMIX(only_l=True, **kwargs).T, 7220.8089999999975)
    assert_allclose(APISRKMIX(only_g=True, **kwargs).T, 140184.08901758507)
    
    # PR - switching between roots
    kwargs = dict(Tcs=[768.0], Pcs=[1070000.0], omegas=[0.8805], kijs=[[0.0]], zs=[1], P=59948425.03189249, V=0.0010511136321381571)
    assert_allclose(PRMIX(**kwargs).T, 8494.452309870687)
    assert_allclose(PRMIX(only_l=True, **kwargs).T, 8494.452309870687)
    assert_allclose(PRMIX(only_g=True, **kwargs).T, 8497.534359083393)
    
    # PRSV - getting correct high T root
    obj = PRSVMIX(Tcs=[768.0], Pcs=[1070000.0], omegas=[0.8805], kijs=[[0]], kappa1s=[0.0], zs=[1], P=101325.0, V=0.0006516540616638367, only_g=True)
    assert_allclose(obj.T, 53063.095694269345)

    obj = PRSVMIX(Tcs=[768.0], Pcs=[1070000.0], omegas=[0.8805], kijs=[[0]], kappa1s=[0.0], zs=[1], P=101325.0, V=0.0006516540616638367, only_l=True)
    assert_allclose(obj.T, 633.5943456378642)
    
    # RK - formula just dies, need numerical
    obj = RKMIX(Tcs=[768.0], Pcs=[1070000.0], omegas=[0.8805], kijs=[[0.0]], zs=[1], V=0.0005170491466536438, P=1.048113134154686, only_l=True)
    assert_allclose(obj.T, 0.0013894955646342926)
    
    # PRSV - issue where wrong a_alpha  was stored
    a_alpha_PT = PRSVMIX(Tcs=[768.0], Pcs=[1070000.0], omegas=[0.8805], kijs=[[0]], kappa1s=[0.0], zs=[1],T=2000, P=1121481.0535455043).a_alpha
    a_alpha_PV = PRSVMIX(Tcs=[768.0], Pcs=[1070000.0], omegas=[0.8805], kijs=[[0]], kappa1s=[0.0], zs=[1],V=0.015290731096352726, P=1121481.0535455043, only_l=True).a_alpha
    assert_allclose(a_alpha_PT, a_alpha_PV, rtol=1e-12)


def TV_PV_precision_issue():
    base = PRMIXTranslatedConsistent(Tcs=[512.5], Pcs=[8084000.0], omegas=[0.559],  zs=[1], T=0.0013894954943731374, P=2.947051702551812)
    V_err = base.volume_error()
    assert V_err < 1e-15
    
    PV_good = PRMIXTranslatedConsistent(Tcs=[512.5], Pcs=[8084000.0], omegas=[0.559], zs=[1], P=base.P, V=base.V_l_mpmath)
    TV_good = PRMIXTranslatedConsistent(Tcs=[512.5], Pcs=[8084000.0], omegas=[0.559], zs=[1], T=base.T, V=base.V_l_mpmath)
    
    with pytest.raises(Exception):
        TV_bad = PRMIXTranslatedConsistent(Tcs=[512.5], Pcs=[8084000.0], omegas=[0.559], zs=[1], T=base.T, V=base.V_l)
    
    PV_bad = PRMIXTranslatedConsistent(Tcs=[512.5], Pcs=[8084000.0], omegas=[0.559], zs=[1], P=base.P, V=base.V_l)
    # except
    assert_allclose(base.T, PV_good.T, rtol=1e-15)
    assert_allclose(base.P, TV_good.P, rtol=1e-15)
    
    # No matter what I do, the solved T is at maximum precision! Cannot go lower without more prec
    assert abs(PV_bad.T/base.T-1) < 1e-7
    
    # Different case
    base = PRMIXTranslatedConsistent(Tcs=[33.2], Pcs=[1296960.0], omegas=[-0.22], zs=[1], T=10000, P=596362331.6594564)
    TV = base.to(V=base.V_l, T=base.T)
    PV = base.to(V=base.V_l, P=base.P)
    assert_allclose(TV.P, base.P, rtol=1e-11)
    assert_allclose(PV.T, base.T, rtol=1e-11)