#!/usr/bin/env python
#
# OVERVIEW:
# - hvcc needs to be run on the input file (with appropriate flags for generating project.
# - each of the "GENERATE" sections need to do certain things related to the Heavy_<PatchName>.cpp/.hpp generated files
# - new output folder is created with the puredata files' name, containing new project.
# - optionally, we could have it build the example after, but that'd require bringing the toolchain along for the ride.
#
# * INCLUDES: need to include the generated "Heavy_PatchName.hpp" file
# * GLOBALS: need to declare Heavy_PatchName object with samplerate set.
# * AUDIOCALLBACK:
#     * Send float parameters to Heavy_PatchName object via Heavy_PatchName::sendFloatToReceiver()
#     * call Heavy_PatchName object's process function
# * PREINIT: 
#     * probe Heavy object for number of channels and control data.
#     * configure Audio for 2 or 4 channel audio depending.
# * POSTINIT: 
#     * configure daisy::Parameter objects with same min/max and linear curve settings for passing to Heavy
#     * sendFloatToReceiver for all defaults.
#
# TODO:
# * Add json or yaml meta data file for board info (details on controls, names, etc.)
# * Determine how to handle non-analog controls like buttons, encoders, etc.
# * Determine how to handle the DaisySeed / DaisyBoard difference for lack of hw.Configure() or not.
#     for now it can be detected/generated into the PREINIT section.
#
import os
import argparse
import subprocess
import shlex
import shutil
import sys
import fileinput
#import hvcc.hvcc as hv
print(sys.path)
#sorry for all the global vars....
basename = ''
filename = ''
board = ''

def searchReplace(file, find, replace):
    f = open(file,'r')
    filedata = f.read()
    f.close()

    newdata = filedata.replace(find, replace)

    f = open(file,'w')
    f.write(newdata)
    f.close()

paths = {
    "Directory" : "",
    "Template" : "",
    "Makefile" : "",
    "Boards" : ""
}
    
replaceComments = {
    "Includes"  :  "// GENERATE INCLUDES",
    "Globals"   :  "// GENERATE GLOBALS",
    "Preinit"   :  "// GENERATE PREINIT",
    "ADC"       :  "// GENERATE ADC",
    "Loop"      :  "// GENERATE INFINITELOOP",
    "Debounce"  :  "// GENERATE DEBOUNCE",
    "Controls"  :  "// GENERATE CONTROLS",
    "Target"    :  "# GENERATE TARGET",
    "Board"     :  "// GENERATE BOARD",
    "Progpath"  :  "GENERATE_PROGPATH"
}
    
def generateCpp():
    #Includes
    searchReplace(paths["Template"], replaceComments["Includes"], '#include "c/Heavy_' + basename + '.hpp"')

    #Globals
    searchReplace(paths["Template"], replaceComments["Globals"], 'Heavy_' + basename + ' hv(SAMPLE_RATE);')
        
    #Preinit
    st = ''
    if (board == 'seed'):
        st = 'hardware->Configure();'
    searchReplace(paths["Template"], replaceComments["Preinit"], st)

    #ADC
    st = ''
    if (board != "seed"):
        st = 'hardware->StartAdc();'
    searchReplace(paths["Template"], replaceComments["ADC"], st)

    #InfiniteLoop
    if (board == 'patch'):
        searchReplace(paths["Template"], replaceComments["Loop"], 'hardware->DisplayControls(false);')
    
    #Debounce
    if (board != "seed"):
        searchReplace(paths["Template"], replaceComments["Debounce"], 'hardware->DebounceControls();\nhardware->UpdateAnalogControls();')

    #Controls
    if(board == "seed"):
        searchReplace(paths["Template"], replaceComments["Controls"], "hv.sendFloatToReceiver(info.hash, 0.f);")

        
def generateMakefile():
    searchReplace(paths["Makefile"], replaceComments["Target"], 'TARGET = ' + basename)
    searchReplace(paths["Makefile"], replaceComments["Progpath"], paths["Progpath"])

def generateBoard():
    #board type
    searchReplace(paths["Board"], replaceComments["Board"], '#define DSY_BOARD Daisy' + board.capitalize())    

    #remove comments around board init stuff
    searchReplace(paths["Board"], "/* " + board, "")
    searchReplace(paths["Board"], board + " */", "")    
    
replaceFunctions = {
    "Includes" : generateCpp,
    "Makefile" : generateMakefile,
    "Board"    : generateBoard
}

def main():
    parser = argparse.ArgumentParser(description='Utility for converting Puredata files to Daisy projects, uses HVCC inside')
    parser.add_argument('pd_input', help='path to puredata file.')
    parser.add_argument('-b',  '--board', help='hardware platform for generated output.', default='seed')
    parser.add_argument('-p',  '--search_paths', action='append', help="Add a list of directories to search through for abstractions.")
    parser.add_argument('-c',  '--hvcc_cmd', type=str, help="hvcc command.", default='python hvcc/hvcc.py')
    parser.add_argument('-o', '--out_dir', help="dir for generated code")

    args = parser.parse_args()
    ctx = argparse.Namespace()
    inpath = os.path.abspath(args.pd_input)
    search_paths = args.search_paths or []

    global basename
    basename = os.path.basename(inpath).split('.')[0]

    #template filename
    global filename
    filename = basename + '.cpp'

    global board
    board = args.board.lower()
    print("Converting {} for {} platform".format(basename, board))

    ctx.progpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    ctx.basename = basename
    ctx.filename = filename
    ctx.board = board
    ctx.out_dir = basename
    if args.out_dir:
        ctx.out_dir = args.out_dir

    # paths to headers and libs are relative to this program,
    # so make sure we are where the program is.
    os.chdir(ctx.progpath)
    #print("Working directory is now {}".format(progpath))

    # run heavy
    os.mkdir(ctx.out_dir)
    command = '{} {} {} -o {} -n {} -g c'.format(args.hvcc_cmd, inpath, ' '.join('-p '+p for p in search_paths), ctx.out_dir, basename)
    print('Executing {}'.format(command))
    # An uninstalled hvcc needs to see Python packages relative to the repo root.
    # env = os.environ
    # env['PYTHONPATH'] = os.path.dirname(os.path.abspath(args.hvcc_cmd))
    process = subprocess.run(shlex.split(command))
    if process.returncode:
        sys.exit(process.returncode)

    # Copy over template.cpp and daisy_boards.h
    for srcfile in ('util/template.cpp', 'util/Makefile', 'util/daisy_boards.h'):
        shutil.copy(srcfile, ctx.out_dir)

    #paths to files, and move template
    paths["Directory"] = ctx.out_dir
    paths["Template"] = os.path.join(ctx.out_dir, filename)
    os.rename(os.path.join(ctx.out_dir, 'template.cpp'), paths["Template"])
    
    paths["Makefile"] = os.path.join(ctx.out_dir, 'Makefile')        
    paths["Board"] = os.path.join(ctx.out_dir, 'daisy_boards.h')
    paths["Progpath"] = ctx.progpath
    paths["Outdir"] = ctx.out_dir

    for i in replaceFunctions:
        replaceFunctions[i]()

    print('Generated code is at {}'.format(ctx.out_dir))

if __name__ == "__main__":
    main()
