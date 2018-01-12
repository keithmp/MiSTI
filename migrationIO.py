#!/usr/bin/env python3
import sys
def ReadPSMCFile(fn, RD = -1):
    maxRD = -1
    Tk = []
    Lk = []
    th = 0
    
    with open(fn) as f:
        for line in f:
            line = line.split()
            if line[0] == "RD":
                maxRD = int( line[1] )
        if maxRD == -1:
            print("Corrupted of empty input file")
            sys.exit(0)
        if RD == -1 or RD > maxRD:
            RD = maxRD

    with open(fn) as f:  
        for line in f:
            line = line.split()
            if line[0] != "RD" or int( line[1] ) != RD:
                continue
            while line[0] != "RS":
                if line[0] == "TR":
                    th = float(line[1])
                line = next(f)
                line = line.split()
            while line[0] != "PA":
                if line[0] != "RS":
                    print("Unexpected line.")
                    sys.exit(0)
                Tk.append( float(line[2]) )
                Lk.append( float(line[3]) )
                line = next(f)
                line = line.split()
            break
    data = [Tk, Lk, RD, th]
    return( data )

def ReadPSMC(fn1, fn2, RD = -1, collapse = False):
    d1 = ReadPSMCFile(fn1, RD)
    d2 = ReadPSMCFile(fn2, RD)
    if d1[2] != d2[2]:
        print("Different RDs for input files 1 and 2.")
        sys.exit(0)
    d2[0] = [v*d1[3]/d2[3] for v in d2[0]]#rescale   time       by th1/th2
    d2[1] = [v*d2[3]/d1[3] for v in d2[1]]#rescale   epsize     by th2/th1 (compare with previous line!)
    Tk = []
    Lk1 = []
    Lk2 = []
    Tk = sorted( d1[0] + d2[0][1:] )
    j = 0
    for i in range( len(d1[0]) - 1 ):
        while Tk[j] < d1[0][i + 1]:
            Lk1.append( 1.0/d1[1][i] )
            j += 1
    while len(Lk1) < len(Tk):
        Lk1.append(1.0/d1[1][-1])
    print(len(Tk))
    print(len(Lk1))
    for i in range(len(Tk)):
        print(1/Lk1[i], "\t", Tk[i])

fn1 = sys.argv[1]
fn2 = sys.argv[2]
ReadPSMC(fn1, fn2)