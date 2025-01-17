#!/usr/bin/env python

import os
import sys
import argparse
import subprocess
from omg.gaussian.gaussian import GaussianLog as GAULOG
from omg.gaussian.gaussian import GaussianCom as GAUCOM
from omg import atoms
from omg import iolines

def pts_to_int(pts):
    try:
        pts = int(pts) - 1
        return int(pts)
    except:
        if pts =='all':
            return pts
        else:
            usage()
            sys.stderr.write('bad input:\n')
            sys.stderr.write('  expected int or all, but got %s:\n' % pts)
            sys.exit(2)

def get_args():
    "Parse arguments of gau_makepdb"
    parser = argparse.ArgumentParser(
        description="""
            Extract structures from gaussian .log or .com files
            and make .pdb files for visualization in VMD or Pymol.""",
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('gau', help='Gaussian .log or .com file')
    parser.add_argument('-s', '--scan_step',
                        help='Scan step ("all" or integer) default="all"',
                        default='all')
    parser.add_argument('-o', '--opt_step',
                    help='Scan step ("all" or integer) default = last = 0"',
                        default='0')
    parser.add_argument('-n', '--nohighlayer',
                    help='Dont make .pdb for highlayer only',
                    action='store_true', default=False)
    parser.add_argument('--pdb', help='Name for output .pdb file')
    parser.add_argument('--pdbh', help='Name .pdb file with high layer only')
    parser.add_argument('--align',
                    help='Request Pymol alignment', default=False,
                    action='store_true')
    args = parser.parse_args()

    # parse input extension
    basename, input_extension = os.path.splitext(args.gau)
    if input_extension not in ['.log', '.com']:
        sys.stderr.write('Aborting!\n')
        sys.stderr.write('  inputname suffix is: %s\n' % input_extension)
        sys.stderr.write('  must be ".com" or ".log"\n')
        sys.exit(2)
    args.ext = input_extension
    args.base = basename

    # highlayer
    args.highlayer = not args.nohighlayer
    if args.pdbh and args.nohighlayer:
        sys.stderr.write('CONFLICTING OPTIONS:\n')
        sys.stderr.write('  --pdbh and --nohighlayer\n')
        sys.stderr.write('Aborting.\n')
        sys.exit(2)

    # output
    if not args.pdb:
        args.pdb = args.base + '.pdb'
    if args.highlayer and not args.pdbh:
        args.pdbh = args.base + '.highlayer.pdb'

    # scan and opt steps
    args.scan_step = pts_to_int(args.scan_step)
    args.opt_step  = pts_to_int(args.opt_step)

    return args

 
def write_pdb(gaulog, scan_pts, opt_pts):

    # get the bytes
    chosen_bytes = []
    if scan_pts == 'all':
        for sbytes in gaulog.grep_bytes['orientation:']:
            if opt_pts == 'all':
                for byte in sbytes:
                    chosen_bytes.append(byte) # this is crazy
            else:
                chosen_bytes.append(sbytes[opt_pts])
    else:
        sbytes = gaulog.grep_bytes['orientation:'][scan_pts]
        if opt_pts == 'all':
            for byte in sbytes:
                chosen_bytes.append(byte) # this is reasonable 
        else:
            chosen_bytes.append(sbytes[opt_pts])

    # produce txt output
    txt = ''
    txth = ''
    model_number = 0
    for byte in chosen_bytes:
        model_number += 1
        xyz = gaulog.read_coordinates('all', byte)
        counter = 0 
        txt += 'MODEL %d\n' % model_number
        txth += 'MODEL %d\n' % model_number
        for (coords, atom) in zip(xyz, gaulog.atoms_list):
            counter += 1 # consistent with gaussian line number
            atom.SetVector(coords[0],coords[1],coords[2])
            atom.set_pdbinfo(atoms.PDBinfo('ATOM', counter))
            txt += iolines.atom2pdb(atom)
            if atom.oniom and args.highlayer:
                if atom.oniom.layer == 'H':
                    txth += iolines.atom2pdb(atom)
        txt += 'ENDMDL\n'
        txth += 'ENDMDL\n'
    return txt, txth

def main():
    
    args = get_args()

    # .com file ?
    if args.ext == '.com':
        gaucom = GAUCOM(args.gau)
        txt = ''
        txth = ''
        for (i,at) in enumerate(gaucom.atoms_list):
            at.set_pdbinfo(atoms.PDBinfo('ATOM', i))
            txt += iolines.atom2pdb(at)
            if at.oniom and args.highlayer:
                if at.oniom.layer == 'H':
                    txth += iolines.atom2pdb(at)

        with open(args.pdb, 'w') as o:
            o.write(txt)

        if args.highlayer:
            print 'here'
            with open(args.pdbh, 'w') as o:
                o.write(txth)
        
        return 0

    # Gaussian .log
    gaulog = GAULOG(args.gau)
    txt, txth = write_pdb(gaulog, args.scan_step, args.opt_step)
    with open(args.pdb, 'w') as o:
        o.write(txt)
    if args.highlayer:
        with open(args.pdbh, 'w') as o:
            o.write(txth)

    # Alignment Pymol
    if 'all' not in [args.scan_step, args.opt_step] or not args.align:
        return 0

    print ('Aligning with pymol...')
    
    # MORE MAGIC: Use pymol for alignment
    o = args.pdb
    b = os.path.splitext(o)[0]
    txt  = 'cmd.load("%s", format="pdb", multiplex=0)\n' % o
    txt += 'cmd.intra_fit("%s", state=0)\n' % b
    txt += 'cmd.save("%s", selection="%s", state=0, format="pdb")\n' % (o, b)
    txt += 'cmd.quit\n'
    with open('.temp_pymolscript.pml', "w") as temp_pymolscript:
        temp_pymolscript.write(txt)

    subprocess.call('pymol -qc .temp_pymolscript.pml', shell=True)
    subprocess.call('rm .temp_pymolscript.pml', shell=True)
    
    return 0

if __name__ == '__main__':
    main()



