#!/usr/bin/env python3
import sys
from migrationIO import PrintJAFSFile

if len(sys.argv) < 2:
    print("./ANGSDSFS.py <INPUT FILE>")
    exit(0)

fn = sys.argv[1]
jaf = [0 for _ in range(7)]

with open(fn) as f:
    for line in f:
        freqs = line.split(" ")
        for i in range(1, 8):
            jaf[i-1] += float( freqs[i] )

jaf = [round(u) for u in jaf]
PrintJAFSFile(jaf)
