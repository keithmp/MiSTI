#!/usr/bin/env python3

import sys
import collections
import numpy
from scipy import (linalg,optimize)
from numpy import (dot,identity,mat)
import math
from math import (exp,log)
import time
if False:
    import matplotlib.pyplot as plt
import multiprocessing

from CorrectLambda import CorrectLambda
from TwoPopulations import TwoPopulations
from OnePopulation import OnePopulation


class MigrationInference:
    COUNT_LLH = 0
    CORRECTION_CALLED = 0
    CORRECTION_FAILED = 0
    
    def __init__(self, times, lambdas, dataJAFS, mu, splitT, theta, **kwargs):
        self.debug = False
        self.enableOutput = False
        if "debug" in kwargs:
            if kwargs["debug"]:
                self.debug = True
                self.enableOutput = True
        if "enableOutput" in kwargs:
            if kwargs["enableOutput"]:
                self.enableOutput = True
        if self.enableOutput:
            print("MigrationInference: output enabled.")
        
        self.correct = True
        if "correct" in kwargs:
            if not kwargs["correct"]:
                self.correct = False
        self.smooth = False
        if "smooth" in kwargs:
            if kwargs["smooth"]:
                self.smooth = True
        
        #Model parameters
        self.theta = theta#coalescent mutation rate theta/2
        self.splitT = splitT
        self.mu = mu
        
        #PSMC parameters
        self.lh = lambdas#pairs of PSMC lambda_0 and lambda_1
        self.times = times
        self.numT = len(self.lh)#number of time intervals
        if len(self.times) != self.numT - 1:
            print("Unexpected number of time intervals")
            sys.exit(0)
        
        #Data parameters
        #Joint allele frequency spectrum: 0100,1100,0001,0101,1101,0011,0111
        self.dataJAFS = dataJAFS
        
        #Class variables
        self.lc = [[1,1] for i in range(self.numT)]#Corrected lambdas
        self.M = None#Differential equation matrix
        self.integralP = None#Integral of dif eq solution
        self.P0 = None#Initial condition for dif eq
        self.P1 = None#Values of solution at the end of the interval
        self.JAFS = [0 for i in range(7)]#Joint allele frequency spectrum: 0100,1100,0001,0101,1101,0011,0111
        
        #Class for EP size correction
        self.cl = CorrectLambda()
        self.cl.SetMu(mu[0], mu[1])
        
        #Plotting options - TODO
        self.doPlot = False
        if "doPlot" in kwargs:
            if kwargs["doPlot"]:
                self.doPlot = True
                self.scaleEPS = 1
                self.scaleT = 1
                if "scaleEPS" in kwargs:
                    self.scaleEPS = float(kwargs[scaleEPS])
                if "scaleT" in kwargs:
                    self.scaleT = float(kwargs[scaleT])
        
        print("MigrationInference class initialized. Class size", self.numT)
      
    def PrintError(self, func, text):
        func = func + "():"
        print("MigrationInference class error in function", func, text)
        sys.exit(0)
      
    def CorrectLambdas(self):
        MigrationInference.CORRECTION_CALLED += 1
        p0 = [[1,0,0],[0,1,0]]
        nc = [0, 0]#Probability for not coalescing
        for t in range(self.splitT):
#            print(self.lh[t])
#            print(self.times[t])
#            print(p0)
            if not self.correct or self.mu[0] + self.mu[1] == 0:
                self.lc[t][0],self.lc[t][1] = self.lh[t][0],self.lh[t][1]
            else:
                self.cl.SetInterval(self.lh[t], self.times[t], p0)
                try:
                    sol = self.cl.SolveLambdaSystem()
                except optimize.nonlin.NoConvergence:
                    print("lh=", self.lh[t])
                    print("t=", self.times[t])
                    print("mu=", self.mu)
                    print("p0=", p0)
                    MigrationInference.CORRECTION_FAILED += 1
                    sys.exit(0)
                    return False
                if self.enableOutput:
                    print("lh=", self.lh[t])
                    print("lc=", sol[0])
                    print("t=", self.times[t])
                    print("initial conditions", p0[0], "\t", p0[1])
    #            print("interval solution\t",sol)
                self.lc[t][0],self.lc[t][1] = sol[0][0],sol[0][1]
                if sol[0][0] < 0 or sol[0][1] < 0:
                    MigrationInference.CORRECTION_FAILED += 1
                    return False
                p0 = sol[1]
            nc[0] += -self.times[t]*self.lh[t][0]
            nc[1] += -self.times[t]*self.lh[t][1]
        for t in range(self.splitT,self.numT - 1):
#            self.lc[t][0],self.lc[t][1] = (self.lh[t][0]+self.lh[t][1])/2,(self.lh[t][0]+self.lh[t][1])/2
            if self.times[t] == 0:
                self.lc[t][0], self.lc[t][1] = 1, 1
                continue
            pnc = ( exp(-self.times[t]*self.lh[t][0]) + exp(nc[1] - nc[0] - self.times[t]*self.lh[t][1]) )/( 1 + exp( nc[1] - nc[0] ) )
            self.lc[t][0] = -log(pnc)/self.times[t]
            self.lc[t][1] = -log(pnc)/self.times[t]
            if self.times[t] == 0:
                continue
            nc[0] += -self.times[t]*self.lc[t][0]
            nc[1] += -self.times[t]*self.lc[t][1]
        t = self.numT - 1
        self.lc[t][0],self.lc[t][1] = (self.lh[t][0]+self.lh[t][1])/2,(self.lh[t][0]+self.lh[t][1])/2
        self.Smooth()
        return True
    
    def Smooth(self):
        if not self.smooth:
            return
#        self.SmoothSplitTime(2, 2)
        self.SmoothConst(0)
        self.SmoothConst(1)
    
    def SmoothConst(self, indiv):
        k = 0
        lam = self.lh[indiv][0]
        time = 0.0
        nc = 0.0
        while k < self.numT-1:#FIXME - last interval is not treated correctly
            j = k
            while abs(self.lh[j][indiv]-lam) < 1e-10 and j < self.numT-1:
                nc += self.lc[j][indiv]*self.times[j]
                time += self.times[j]
                j += 1
            for i in range(k, j):
                self.lc[i][indiv] = nc/time
            lam = self.lh[j][indiv]
            nc = 0.0
            time = 0.0
            k = j
                
        
    
    def SmoothInterval(self, interval, left, right = None):
        if not self.smooth:
            return
        if right == None:
            right = left
        if interval - left < 0:
            text = "Unexpected value for left smoothing: " + str(left) + ", value cannot be larger than " + str(interval)
            self.PrintError("SmoothInterval", text)
        if interval + right - 1 >= self.numT:
            text = "Unexpected value for right smoothing: " + str(right) + ", value cannot be larger than " + str(self.numT - interval + 1)
            self.PrintError("SmoothInterval", text)
        ncSmInt = [0, 0]
        sumT = 0
        for k in [0, 1]:
            for i in range(interval - left, interval + right):
                ncSmInt[k] += -self.lc[i][k]*self.times[i]
        for i in range(interval - left, interval + right):
            sumT += self.times[i]
        nc = [0, 0]
        for k in [0, 1]:
            for i in range(self.splitT - left):
                nc[k] += -self.lc[i][k]*self.times[i]
        pnc = (1 + exp(nc[1] - nc[0] + ncSmInt[1] - ncSmInt[0])) / (1 + exp(nc[1] - nc[0]))
        pnc = ncSmInt[0] + log(pnc)
        lsmoothed = - pnc / sum(times[self.splitT - left:self.splitT + right])
        lsmoothed = - ncSmInt[0]/sumT
        for k in [0, 1]:
            for i in range(self.splitT - left, self.splitT + right):
                self.lc[i][k] = lsmoothed
    
    def SmoothSplitTime(self, left, right = None):
        if not self.smooth:
            return
        if right == None:
            right = left
        if self.splitT - left < 0:
            text = "Unexpected value for left smoothing: " + str(left) + ", value cannot be larger than " + str(self.splitT)
            self.PrintError("SmoothSplitTime", text)
        if self.splitT + right - 1 >= self.numT:
            text = "Unexpected value for right smoothing: " + str(right) + ", value cannot be larger than " + str(self.numT - self.splitT + 1)
            self.PrintError("SmoothSplitTime", text)
        ncSmInt = [0, 0]
        sumT = 0
        for k in [0, 1]:
            for i in range(self.splitT - left, self.splitT + right):
                ncSmInt[k] += -self.lc[i][k]*self.times[i]
        for i in range(self.splitT - left, self.splitT + right):
            sumT += self.times[i]
        nc = [0, 0]
        for k in [0, 1]:
            for i in range(self.splitT - left):
                nc[k] += -self.lc[i][k]*self.times[i]
        pnc = (1 + exp(nc[1] - nc[0] + ncSmInt[1] - ncSmInt[0])) / (1 + exp(nc[1] - nc[0]))
        pnc = ncSmInt[0] + log(pnc)
        lsmoothed = - pnc / sum(times[self.splitT - left:self.splitT + right])
        lsmoothed = - ncSmInt[0]/sumT
        for k in [0, 1]:
            for i in range(self.splitT - left, self.splitT + right):
                self.lc[i][k] = lsmoothed
    
    def JAFSpectrum(self):
        model = TwoPopulations(self.lc[0][0], self.lc[0][1], 1.0, 1.0)
        self.P0 = [0.0 for i in range( model.MSize() )]
        self.P0[2] = 1.0
        for interval in range(self.numT):
            if interval < self.splitT:
                if interval == self.numT - 1 and self.mu[0] + self.mu[1] == 0:
                    self.PrintError("JAFSpectrum", "Infinite coalescent time. No migration.")
                model = TwoPopulations(self.lc[interval][0], self.lc[interval][1], self.mu[0], self.mu[1])
            else:
                model = OnePopulation(self.lc[interval][0])
            if interval == self.splitT:
                self.CollapsePops()
            self.M = model.SetMatrix()
            self.P0 = model.SetInitialConditions(self.P0)
            self.SolveDifEq(interval)
            self.P0 = model.UpdateInitialConditions(self.P1)
            if interval < self.numT - 1:
                self.integralP = model.UpdateIntegral(self.integralP, self.times[interval])
            for i in range( model.StateNum() ):
                jaf = model.StateToJAF(i)
                self.JAFS = [x + y*self.integralP[i] for x,y in zip(self.JAFS, jaf)]
    
    def PrintMatrix(self):
        matSize = self.M.shape[0]
        for i in range(matSize):
            for j in range(matSize):
                el = format(self.M.item(i,j), '.10g')
             #   if int(el) == 0:
             #       el = '.'
                print( el, end = "\t" )
            print("")
    
    def CollapsePops(self):
        Pc = [0 for i in range(8)]
        Pc[0] = sum(self.P0[0:9])
        Pc[1] = sum(self.P0[9:15])
        Pc[2] = sum(self.P0[15:23])
        Pc[3] = sum(self.P0[23:29])
        Pc[4] = sum(self.P0[29:33])
        Pc[5] = sum(self.P0[33:37])
        Pc[6] = sum(self.P0[37:41])
        Pc[7] = sum(self.P0[41:44])
        self.P0 = Pc
    
    def SolveDifEq(self, interval):
        sizeM = self.M.shape[0]
        if interval < self.numT - 1:
            T = self.times[interval]
            MET = linalg.expm( dot(self.M,T) )
            self.P1 = dot(MET,self.P0)
        else:
            self.P1 = [0 for i in range( len(self.P0) )]
        MI = linalg.inv(self.M)
        self.integralP = [x - y for x, y in zip(self.P1, self.P0)]
        self.integralP = dot(MI,self.integralP)
        
    def JAFSLikelyhood(self, mu):
        MigrationInference.COUNT_LLH += 1
        if mu[0] < 0 or mu[1] < 0:
            return float('-inf')
        self.mu[0],self.mu[1]=mu[0],mu[1]
        self.cl.SetMu(mu[0], mu[1])
        res = self.CorrectLambdas()
        if not res:
            return float('-inf') # -10**(10)
        if self.enableOutput:
            print("JAFSLikelyhood(): corrected values of lambdas are", self.lc)
        self.JAFSpectrum()
        norm = sum(self.JAFS)
        self.JAFS = [v/norm for v in self.JAFS]
        if self.debug:
            print("----------",self.JAFS[0],self.JAFS[1],sep="\t\t")
            print(self.JAFS[2],self.JAFS[3],self.JAFS[4],sep="\t\t")
            print(self.JAFS[5],self.JAFS[6],"----------",sep="\t\t")
            n = 1+1/2+1/3
            print("singletons", (self.JAFS[0]+self.JAFS[2]), 1/n)
            print("doubletons", (self.JAFS[1]+self.JAFS[3]+self.JAFS[5]), 1/(2*n))
            print("tripletons", (self.JAFS[4]+self.JAFS[6]), 1/(3*n))
            print("JAFS = ", self.JAFS)
#        return 0
#        return self.Likelihood()
        llh = 0
        for i in range(7):
#            print("self.dataJAFS[i]", self.dataJAFS[i], "\t\tlog(self.JAFS[i])", log(self.JAFS[i]), "\t\tself.JAFS[i]", self.JAFS[i])
            llh += self.dataJAFS[i]*log(self.JAFS[i])
        return( llh )
    
    def ObjectiveFunction(self, mu):
        return( -exp( self.JAFSLikelyhood( mu ) ) )
    
    def SetSimplex(self):
        mm = max([max(el) for el in self.lh])
        p1 = 2*mm
        return( [[0,0], [p1,0], [0,p1]] )
    
    def Solve1(self):
        print("Start solving the problem.")
        maxVal = 2*self.lh[0][0]
        print("maxVal=", maxVal)
        mu0 = [maxVal/2, maxVal/2]
        mu0 = [0.0, 0.0]
        print("mu0=", mu0)
        print("self.mu=", self.mu)
        initSimp = self.SetSimplex()
        print("Initial simplex ", initSimp)
#        res = optimize.minimize(self.ObjectiveFunction, mu0, method='L-BFGS-B', bounds = ((0, maxVal), (0, maxVal)), options={'gtol': 1e-10, 'disp': True})
        res = optimize.minimize(self.ObjectiveFunction, mu0, method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-4 })#'initial_simplex': initSimp, 
        print(res)
        return([res.x, -res.fun])
#        self.cl = CorrectLambda()
#        res = optimize.minimize(self.ObjectiveFunction, [0,0], method=’L-BFGS-B’, bounds = ((0, None), (0, None)))
#        print(res)
        #print(self.ObjectiveFunction([self.mu[0], self.mu[1]]))
#        optimize ObjectiveFunction(mu0, mu1)
    
    def Solve(self, tol=1e-4):
        maxVal = 2*self.lh[0][0]
        mu0 = [0.0, 0.0]
        res = optimize.minimize(self.ObjectiveFunction, mu0, method='Nelder-Mead', options={'xatol': tol, 'fatol': tol })
        return([res.x, -res.fun])
    
    def MaxLLH(self, muMin = 0.0, muMax = 2.0, step = 0.2, unit = 1):
        muVals = numpy.arange(muMin*unit, muMax*unit+step*unit, step*unit)
        maxllh = 0
        maxmu = [-1, -1]
        for i in muVals:
            for j in muVals:
                llh = exp( self.JAFSLikelyhood([i, j]) )
                if llh > maxllh:
                    maxmu = [i, j]
                    maxllh = llh
        return([maxllh, maxmu])
    
    def Test(self):
        self.ObjectiveFunction([self.mu[0], self.mu[1]])
        
    def Report():
        print("Total number of likelihood function calls is ", MigrationInference.COUNT_LLH)
        print("Lambda correction called ", MigrationInference.CORRECTION_CALLED, " times.")
        print("Lambda correction failed ", MigrationInference.CORRECTION_FAILED, " times.")