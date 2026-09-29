# -*- coding: utf-8 -*-
"""
Created on Thu Jan 5 2023
Updated on Mon Mar 4 2024
1
@author: MEW1PLY, RUM3PLY, BES6FH

Tool to automate CRC patching and software signing process of D4 Tesla Software Releases
Created by: Wegienka Maxwell (CC/ECE1-NA)
Updated by: Emiliano Gonzalez (BGSW/ECC2.3)
"""

import os # Command line interaction
import re # regex functions
import sys # system abort function
from zipfile import ZipFile, ZIP_DEFLATED # zip archive extraction
import shutil # File manpiulation / copying
import hashlib # MD5 hashing for project 2's release report
import html # Escaping text written into the xlsx report
from dataclasses import dataclass # dataclass struct
import ctypes # Ability to call windows c functions
import ctypes.wintypes as wintypes # Ability to use C variable types
import getpass # Hides the PIN input

# Struct to keep address ranges all in one space
@dataclass
class addrRange:
    patchStart: str # Start address for code patch
    patchEnd: str # End address for code patch
    crcLoc: str = None # Start address for CRC
    
@dataclass
class savedCrc:
    fileName: str # File name the CRC is pulled from
    crc: str # CRC found from text file outputted by Hexview

    # Prints in csv format so a stack of them can be placed into a single file
    def printCsv(self):
        return self.fileName + "," + self.crc + "\n"

@dataclass
class savedMd5:
    fileName: str # File name the hash was computed from
    md5: str # MD5 hash of the file contents

defaultAppRangeESP = addrRange("0x30000","0x009b7f9b","0x009b7f9c")
defaultAppRangeIB2 = addrRange("0x28000","0x001b7fcb","0x001b7fcc")
defaultBootRangeESP = addrRange("0x4000","0x00027fcb","0x00027fcc")
defaultBootRangeIB2 = addrRange("0x4000","0x00027fcb","0x00027fcc")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# START WINDOWS DIALOG BOX FUNCTIONS
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~    

LPOFNHOOKPROC = ctypes.c_voidp
LPCTSTR = LPTSTR = ctypes.c_wchar_p

class OPENFILENAME(ctypes.Structure):
    _fields_ = [("lStructSize", wintypes.DWORD),
                ("hwndOwner", wintypes.HWND),
                ("hInstance", wintypes.HINSTANCE),
                ("lpstrFilter", LPCTSTR),
                ("lpstrCustomFilter", LPTSTR),
                ("nMaxCustFilter", wintypes.DWORD),
                ("nFilterIndex", wintypes.DWORD),
                ("lpstrFile", LPTSTR),
                ("nMaxFile", wintypes.DWORD),
                ("lpstrFileTitle", LPTSTR),
                ("nMaxFileTitle", wintypes.DWORD),
                ("lpstrInitialDir", LPCTSTR),
                ("lpstrTitle", LPCTSTR),
                ("flags", wintypes.DWORD),
                ("nFileOffset", wintypes.WORD),
                ("nFileExtension", wintypes.WORD),
                ("lpstrDefExt", LPCTSTR),
                ("lCustData", wintypes.LPARAM),
                ("lpfnHook", LPOFNHOOKPROC),
                ("lpTemplateName", LPCTSTR),
                ("pvReserved", wintypes.LPVOID),
                ("dwReserved", wintypes.DWORD),
                ("flagsEx", wintypes.DWORD)]
    
GetOpenFileName = ctypes.windll.comdlg32.GetOpenFileNameW
GetSaveFileName = ctypes.windll.comdlg32.GetSaveFileNameW

OFN_ENABLESIZING      =0x00800000
OFN_PATHMUSTEXIST     =0x00000800
OFN_OVERWRITEPROMPT   =0x00000002
OFN_NOCHANGEDIR       =0x00000008
MAX_PATH=1024

def _buildOFN(title, default_extension, filter_string, fileBuffer):

  ofn = OPENFILENAME()
  ofn.lStructSize = ctypes.sizeof(OPENFILENAME)
  ofn.lpstrTitle = title
  ofn.lpstrFile = ctypes.cast(fileBuffer, LPTSTR)
  ofn.nMaxFile = MAX_PATH
  ofn.lpstrDefExt = default_extension
  ofn.lpstrFilter = filter_string
  ofn.Flags = OFN_ENABLESIZING | OFN_PATHMUSTEXIST | OFN_OVERWRITEPROMPT | OFN_NOCHANGEDIR
  return ofn

def getOpenFileName(title, default_extension, filter_string, initialPath):
  
  if initialPath is None:
    initialPath = ""
  filter_string = filter_string.replace("|", "\0")
  fileBuffer = ctypes.create_unicode_buffer(initialPath, MAX_PATH)
  ofn = _buildOFN(title, default_extension, filter_string, fileBuffer)
  
  if GetOpenFileName(ctypes.byref(ofn)):
    return fileBuffer[:]
  else:
    return None
  
def getSaveFileName(title, default_extension, filter_string, initialPath):

  if initialPath is None:
    initialPath = ""
  filter_string = filter_string.replace("|", "\0")
  fileBuffer = ctypes.create_unicode_buffer(initialPath, MAX_PATH)
  ofn = _buildOFN(title, default_extension, filter_string, fileBuffer)

  if GetSaveFileName(ctypes.byref(ofn)):
    return fileBuffer[:]
  else:
    return None

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# END WINDOWS DIALOG BOX FUNCTIONS
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Add on to terminal command calls to suppress stdout and stderr output to console as output is irrelevant and distracts from legitimate errors defined in this script
suppressTerminal = " > NUL 2>&1"
# Hexview program path, attempts to find environment variable before resorting to default argument
hexviewExePath = os.getenv("hexview", "C:\\Hexview")
# SignX exe. Since cmd doesn't like calling it normally, this is the way that works
signXExe = "\"C:/Program Files (x86)/Robert Bosch GmbH/SignX/signx.exe\""

def captureCrc(inputFile: str, crcAddr: str):
    """
    Pulls the 4 byte CRC from a hex file and returns the string

    Parameters:
        inputFile: Full path of the hexfile to read
        crcAddr: Hex address of CRC to read

    Returns:
        outputCrc (str): 4 byte CRC is string format (AA BB CC DD)
    """

    # Get end address (start + 4 bytes) of Crc for command
    endAddr = str(hex(int(crcAddr, 16) + 3))
    # Temp txt file for getting the CRCs from Hexview
    tempCrcTxt = tempDir + "\\crc.txt"
    # Command to find CRC in each file
    exportCrc = "cd " + hexviewExePath + " & Hexview /s " + inputFile + " /AR:" + crcAddr + "-" + endAddr + " /XA:32:\" \" -o " + tempCrcTxt
    os.system(exportCrc + suppressTerminal)
    tempFile = open(tempCrcTxt, "r")
    outputCrc = tempFile.readline()
    tempFile.close()
    return outputCrc

def patchFile(inputFile: str, fileAddr: addrRange, outputFile: str = None):
    """
    Patches a given file by calling Hexview from the command prompt

    Parameters:
        inputFile: File to read and patch the CRC
        fileAddr: Addresses required by Hexview to complete the patching
        outputFile: Optional argument to output to a different file

    Returns:
        N/A
    """

    # If no output file specified, patch in place
    if outputFile == None:
        outputFile = inputFile
    
    # TODO: Modify this function to take more than just CS9, we might need that later
    cs9Format = " /CS9:@" + fileAddr.crcLoc + ";" + fileAddr.patchStart + "-" + fileAddr.patchEnd
    command = "cd " + hexviewExePath + " & Hexview /s " + inputFile +  cs9Format + " /XI -o " + outputFile
    os.system(command + suppressTerminal)

def mergeFile(inFile1: str, inFile2: str, outFile: str = None):
    """
    Merges two files into one using Hexview with 0 offset to either file

    Parameters:
        inFile1: First file to merge (If no outputFile, files will merge into here)
        inFile2: Second file to merge
        outFile: Optional file path if merge-in-place is not desired

    Returns:
        N/A
    """

    if outFile == None:
        outFile = inFile1
    
    moFormat = "/MO:" + inFile1 + ";0+" + inFile2 + ";0"
    command = "cd " + hexviewExePath + " & Hexview /s " + moFormat + " /XI -o" + outFile
    os.system(command + suppressTerminal)

def signFile(inFile: str, scPin: str):
    """
    Signs the file by calling SignX.

    Parameters:
        inFile: File to be signed
        scPin: Smart Card PIN SignX credentials
    
    Returns:
        N/A
    """

    command = signXExe + " -f " + inFile + " -s -pw " + scPin
    os.system(command + suppressTerminal)

def exportCode(inFile: str, exportAddr: addrRange, outFile: str = None):
    """
    Exports a block of code from a file based on the addrRange given (Uses Hexview)

    Parameters:
        inFile: File to read hex code from
        exportAddr: AddrRange to read start and end addresses
        outFile: Optional file to export hex code to (otherwise will overwrite inFile)

    Returns:
        N/A
    """

    if outFile == None:
        outFile = inFile

    arFormat = " /AR:" + exportAddr.patchStart + "-" + exportAddr.patchEnd
    command = "cd " + hexviewExePath + " & Hexview /s " + inFile + arFormat + " /XI -o " + outFile
    os.system(command + suppressTerminal)

def fetchBootAddr():
    """
    Prompts the user for the map file, outputs the addresses required for patching

    Parameters:
        N/A

    Returns:
        boot (addrRange): Range of the code to patch and CRC location
    """
    
    sel = 0
    while not sel:
        try: 
            sel = int(input('Enter 1 to select OEMBLDR map file (recommended) or 2 to use hardcoded addresses: '))
            if sel not in (1, 2):
                raise ValueError
        except ValueError:
            sel = 0
            print("Invalid option entered!")

    boot = addrRange("", "", "")

    if sel == 1:
        # This is the dialog box and setup for the boot map file.
        print("Opening the Boot Patch Map File")
        fname = getOpenFileName("Open Boot Patch Map File", ".map", "Map_*.map", os.environ["temp"])
        fname = re.sub("\0", "", fname)
    
        # Pull patch and CRC address from file
        with open(fname) as fn:
            for line in fn:
                if ".hexblockst_bldr" in line:
                    parts = line.split()
                    boot.patchStart = "0x" + parts[1]
                if ".crc32_bldr" in line:
                    parts = line.split()
                    boot.crcLoc = "0x" + parts[1]
                    boot.patchEnd = str(hex(int(boot.crcLoc, 16) - 1))
                if boot.patchStart != "" and boot.patchEnd != "":
                    break
    else:
        boot.patchStart = '0x00004000'
        boot.patchEnd = '0x27fcb'
        boot.crcLoc='0x00027fcc'

    return boot

def fetchCodeCalAddr(mapFile: str):
    """
    Finds the code block and cal block addresses from the map file in the temp directory
    NOTE: This finds both at the same time to reduce the number of file reads
    It might be advantageous to split this is up so we don't have two returns that are only marginally related

    Parameters:
        mapFile: File path for the .map file to read the address ranges from
    
    Returns:
        codeBlock: addrRange containing the start and end addresses of the code itself (Not the export block)
        calBlock: addrRange containing the start and end addresses of the cal code itself (Not the export block)
		paddingBytesEndAddr: string containing end address of the padding bytes. Is only populated if defined in the map file.
    """

    codeBlock = addrRange("", "", "")
    calBlock = addrRange("", "", "")
    paddingBytesEndAddr = "" 

    with open(mapFile) as mf:
        for line in mf:
            try:
                # Code block start
                if codeBlock.patchStart == "" and ".hexblockst_fsw_01" in line:
                    parts = line.split()
                    codeBlock.patchStart = "0x" + parts[1]
                # Code block CRC
                if codeBlock.crcLoc == "" and ".crc32_fsw" in line:
                    parts = line.split()
                    codeBlock.crcLoc = "0x" + parts[1]
                    # Since Start and CRC are given, we can just stick those in
                    # For end, we take (CRC - 1) to get it
                    # Since the starting value and ending value are strings, we get this monstrosity
                    codeBlock.patchEnd = str(hex(int(codeBlock.crcLoc, 16) - 1))
                # Cal block start
                if calBlock.patchStart == "" and ".hexblockst_cal1" in line:
                    parts = line.split()
                    calBlock.patchStart = "0x" + parts[1]
                # Cal block CRC
                if calBlock.crcLoc == "" and ".crc32_cal" in line:
                    parts= line.split()
                    calBlock.crcLoc = "0x" + parts[1]
                    calBlock.patchEnd = str(hex(int(calBlock.crcLoc, 16) - 1))
                # Padding bytes end range
                if paddingBytesEndAddr == "" and ".myPadding_fsw01" in line:
                    parts = line.split()
                    paddingBytesEndAddr = "0x" + parts[1]
            except StopIteration:
                break
            
    return codeBlock, calBlock, paddingBytesEndAddr

def findCodeBlockEnd(inAddr: addrRange):
    """
    Finds the ends of a code block based on the given address range
    NOTE: This is mainly put into place in case the logic here needs to be changed later for different formats.

    Parameters:
        inAddr: Input address range to find the full code block

    Returns:
        outAddr: The addrRange of the full codeBlock
    """

    # Create temp var, copy the start address over
    outAddr = addrRange("","")
    outAddr.patchStart = inAddr.patchStart
    # Change the last three digits of the end address to "0xfff" for end of block
    outAddr.patchEnd = inAddr.patchEnd[:-3] + "fff"
    return outAddr

def copySignedFiles(oldDir: str, newDir: str):
    """
    Copys all signed files that have paths ending in _S.hex
    from the temp directory into the "signed" directory

    Parameters:
        oldDir: Source directory to copy files from
        newDir: Destination directory to copy files into

    Returns:
        N/A
    """

    # NOTE: This does go through the entire folder again looking for files,
    # but this makes it so we don't have to adjust the function if we add a new folder
    for file in os.listdir(oldDir):
        if file.endswith("_S.hex"):
           oldFile = oldDir + "\\" + file
           newFile = newDir + "\\" + file
           shutil.copy(oldFile, newFile) 

def checkSignedFile(signFile: str, currentDir: str):
    """
    Checks if the file passed in was signed and created or not.
    If file does not exist, this function will abort the script to prevent multiple failed attempts at signed from happening (saved the Smart Card from being locked)

    Parameteres:
        signFile: File that was possibly signed, check existance of it
        currentDir: Directory where the file should be located
    """

    # Strip file name to remove the full path
    fileName = os.path.split(signFile)[-1]

    # If file exists, print message confirming it, continue
    if fileName in os.listdir(currentDir):
        print(signFile + " has been successfully signed and saved")
    # If file not found, throw an error and kill the script
    else:
        sys.exit("Script aborted, " + signFile + " could not be found after signing process")

def signFilesBatch(inFiles: list, scPin: str, tempDir: str):
    """
    Signs a list of files in a single batch command by calling SignX
    using a temporary file list as required by the '-l' argument.
    
    Parameters:
        inFiles: A list of file paths to be signed.
        scPin: Smart Card PIN for SignX credentials.
        tempDir: The directory where the temporary file list will be created.
    
    Returns:
        N/A
    """
    # Define the path for the temporary file list inside the temp directory
    file_list_path = os.path.join(tempDir, "sign_file_list.txt")
    print("Creating file list for batch signing...")

    try:
        # 1. Create the file list in ASCII format.
        #    The documentation specifies one file name per line.
        print(f"Creating temporary file list at: {file_list_path}")
        with open(file_list_path, 'w') as f:
            for file_path in inFiles:
                f.write(f"{file_path}\n") # Write each file path on a new line

        # 2. Construct the command using the -l argument.
        command = signXExe + " -l " + file_list_path + " -s -pw " + scPin
        
        print(f"Executing batch signing for {len(inFiles)} files. Please wait...")
        #print(f"DEBUG: Generated command: {command}") # Uncomment for debugging
        
        # 3. Execute the signing command.
        os.system(command)

    finally:
        # 4. Clean up: ensure the temporary file list is deleted after use.
        if os.path.exists(file_list_path):
            os.remove(file_list_path)
            print(f"Temporary file list '{file_list_path}' removed.")

# Extended linear address record marking the start of the CodeBlock's trailing ECC/reserve section
eccBlockMarker = ":020000040FF0"
# Clean Intel-HEX end-of-file record
eofRecord = ":00000001FF\r\n"

def removeEccBlock(inFile: str):
    """
    Strips the CodeBlock's trailing ECC/reserve section (found via eccBlockMarker),
    leaving only the actual code block plus a clean EOF record.

    Parameters:
        inFile: Signed CodeBlock hex file to strip in place

    Returns:
        N/A
    """

    with open(inFile, "r", encoding="ascii", errors="ignore", newline="") as f:
        hexText = f.read()

    eccStart = hexText.find(eccBlockMarker)
    if eccStart == -1:
        # No ECC section found, nothing to strip
        return

    with open(inFile, "w", encoding="ascii", newline="") as f:
        f.write(hexText[:eccStart] + eofRecord)

def computeMd5(inFile: str):
    """
    Computes the MD5 hash of a file's contents.

    Parameters:
        inFile: File to hash

    Returns:
        outputMd5 (str): Hex digest of the file's MD5 hash
    """

    with open(inFile, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def writeMd5ReportXlsx(reportPath: str, hashRows: list):
    """
    Writes a minimal .xlsx workbook (File, MD5 columns) built directly as OOXML,
    mirroring the release report format produced by Gen9_Sign_release_tool_CLI.py.

    Parameters:
        reportPath: Full path of the .xlsx file to create
        hashRows: List of savedMd5 entries to write, one per row

    Returns:
        N/A
    """

    sheetRows = [["File", "MD5"]] + [[row.fileName, row.md5] for row in hashRows]

    def cellRef(rowIndex, columnIndex):
        return chr(ord("A") + columnIndex) + str(rowIndex)

    rowXml = []
    for rowIndex, values in enumerate(sheetRows, start=1):
        cells = []
        for columnIndex, value in enumerate(values):
            escaped = html.escape(value)
            cells.append(f'<c r="{cellRef(rowIndex, columnIndex)}" t="inlineStr"><is><t>{escaped}</t></is></c>')
        rowXml.append(f'<row r="{rowIndex}">{"".join(cells)}</row>')

    sheetXml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(rowXml)}</sheetData></worksheet>'
    )
    workbookXml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="File List" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )

    with ZipFile(reportPath, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", workbookXml)
        archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", sheetXml)

def selectHexPartCandidate(candidates: list):
    """
    Lets the operator choose which (if any) PRJ_HexPart bootloader file belongs to this
    release. Containers can bundle several unrelated bootloader variants, so this can't
    be reliably guessed from the filename alone.

    Parameters:
        candidates: PRJ_HexPart_*.hex file paths found in the extracted container

    Returns:
        Selected file path, or None if no bootloader is part of this release
    """

    if not candidates:
        return None

    print("\nPRJ_HexPart (bootloader) file(s) found in this release:")
    print("  0: None of these belong to this release")
    for index, candidate in enumerate(candidates, start=1):
        print(f"  {index}: {os.path.basename(candidate)}")

    while True:
        try:
            selection = int(input("Enter the number of the bootloader file to sign, or 0 for none: "))
            if 0 <= selection <= len(candidates):
                break
            raise ValueError
        except ValueError:
            print("Invalid option entered!")

    return candidates[selection - 1] if selection > 0 else None

def hexOrApplCont():
    sel = 0
    while not sel:
        try: 
            sel = int(input('Enter 1 to prepare from an ApplContainer only or 2 to prepare from PRJ_HEX from PMSE: '))
            if sel not in (1, 2):
                raise ValueError
        except ValueError:
            sel = 0
            print("Invalid option entered!")
            
    return sel

def selectProject():
    prj = 0
    while not prj:
        try: 
            prj = int(input('Enter 1 to Process ESP project or 2 to Tesla IB2/Rivian project: '))
            if prj not in (1, 2):
                raise ValueError
        except ValueError:
            prj = 0
            print("Invalid option entered!")
            
    return prj

project = selectProject()

choice = hexOrApplCont()

if choice == 1:
    # Find AppContainer
    print("Opening the AppContainer")
    fname = getOpenFileName("Open the AppContainer", ".appl.zip", "*.appl.zip", os.environ["temp"])
    # Removes all null chars to make sure it works in the ZipFile call
    appContainer = re.sub("\0", "", fname)
    
    # Setup working directory and temp directory
    workingDir = os.path.dirname(fname)
    tempDir = workingDir + "\\temp"
    
    # Deletes any old instance of it, builds a new one
    if (os.path.exists(tempDir)):
        shutil.rmtree(tempDir)
    os.mkdir(tempDir)

    # Extract appContainer into tempDir
    with ZipFile(appContainer, "r") as appContain:
        appContain.extractall(path=tempDir)

# User input for Smart card
# PIN is numbers only, so run through until a valid PIN is entered 
SCpin = ""

while True:   
    SCpin = getpass.getpass("Please enter smart card PIN (Input not shown): ")
    try:
        PinNum = int(SCpin)
        break
    except ValueError:
        print("Invalid entry, PIN cannot contain letters")
    
    # Setup working directory and temp directory
    workingDir = os.path.dirname(fname)
    tempDir = workingDir + "\\temp"

# Declare calBlocks arrays first so it dosen't freak on the append functions
calBlocks = [] # Unsigned calBlocks file paths
signedCalBlocks = [] # Signed calBlocks file paths
# Project 2 releases don't always ship a bootloader; collect candidates and only use one if unambiguous
hexPartCandidates = []
hexPartPath = None

# Find needed files, stick their paths into vars
for file in os.listdir(tempDir):
    # hex file(s) to patch
    if file.endswith(".hex"):
        if "PRJ_HexPart" in file:
            if project == 1:
                if "OEMBLDR" in file:
                    hexPartPath = tempDir + "\\" + file
            else:
                hexPartCandidates.append(tempDir + "\\" + file)
        elif "PRJ_Hexfile" in file:
            if choice == 1:
                hexFilePath = tempDir + "\\" + file
            else:
                hexFilePath = tempDir + "\\"
        elif "PRJ_CalBlock" in file:
            if choice == 1:
                calBlocks.append(tempDir + "\\" + file)
        elif "PRJ_CodeBlock" in file:
            codeBlockFilePath = tempDir + "\\" + file
    # map file(s) with needed addresses
    elif file.endswith(".map"):
        mapFilePath = tempDir + "\\" + file

# Project 2's bootloader candidates can't be told apart by filename alone; ask the operator
if project == 2:
    hexPartPath = selectHexPartCandidate(hexPartCandidates)

# Declare and init the addrRanges used for the different sets of code blocks
if project == 1:
    bootAddr = fetchBootAddr()
else:
    # Project 2 (IB2/Rivian) uses a fixed boot CRC location; no interactive map prompt needed
    bootAddr = defaultBootRangeIB2
bootBlock0Addr = findCodeBlockEnd(bootAddr)
codeAddr, calAddr, paddingBytesEndAddr = fetchCodeCalAddr(mapFilePath)
codeExportAddr = findCodeBlockEnd(codeAddr)
calExportAddr = findCodeBlockEnd(calAddr)
        
if choice == 2:
    
    print("Opening the PRJ_HEX File")
    fname = getOpenFileName("Open PRJ_HEX File", ".hex", "PRJ*.hex", os.environ["temp"])
    fname = re.sub("\0", "", fname)
    
    p, n = os.path.split(fname)
    
    hexFilePath = hexFilePath + n
    
    shutil.copy(fname, hexFilePath)
    
    calName = str(input("Enter variant name for CAL block: "))
    calBlockFilePath = tempDir + "\\" + "PRJ_CalBlock_" + calName + ".hex"
            
    exportCode(fname, calExportAddr, calBlockFilePath)
            
    calBlocks.append(calBlockFilePath)
    
    done = 0
    while not done:
        try: 
            moreFiles = str(input('Are there more PRJ_HEX files for other variants? [y/n]: '))
            if moreFiles not in ('y', 'n'):
                raise ValueError
                
            if moreFiles == 'y':
                print("Opening the PRJ_HEX File")
                fname = getOpenFileName("Open PRJ_HEX File", ".hex", "PRJ*.hex", os.environ["temp"])
                fname = re.sub("\0", "", fname)
            
                calName = str(input("Enter variant name for CAL block: "))
                calBlockFilePath = tempDir + "\\" + "PRJ_CalBlock_" + calName + ".hex"
            
                exportCode(fname, calExportAddr, calBlockFilePath)
            
                calBlocks.append(calBlockFilePath)
                
            else:
                done = 1

        except ValueError:
            done = 0
            print("Invalid option entered!")
    
# Any other hex files needed (The signed ones)
# Create file path for signed hexFile
signedHexFilePath = re.sub(".hex", "_S.hex", hexFilePath)
# File path for the signed HexPart file (needs to be signed before use), if a bootloader is part of this release
signedHexPartPath = re.sub(".hex", "_S.hex", hexPartPath) if hexPartPath else None
# Signed codeBlock path used for exporting Block 0 of HexFile
signedCodeBlockFilePath = re.sub(".hex", "_S.hex", codeBlockFilePath)
# --- File Preparation and Collection ---
# This section prepares files (e.g., patching) and gathers them for a single signing step.

files_to_sign = []
signedCalBlocks = [re.sub(".hex", "_S.hex", cal) for cal in calBlocks]

print("Preparing files for signing...")

if project == 1:
    # Prepare and collect files for signing
    files_to_sign.append(hexPartPath)
    
    # Patch hexfile before adding it to the sign list
    patchFile(hexFilePath, codeAddr)
    patchFile(hexFilePath, calAddr)
    files_to_sign.append(hexFilePath)
    
    # Patch each calibration block before adding to the sign list
    for cal in calBlocks:
        patchFile(cal, calAddr)
        files_to_sign.append(cal)
else: # project == 2 (IB2/Rivian): sign the files as-is, no CRC patching is applicable to this chip
    if hexPartPath:
        files_to_sign.append(hexPartPath)

    files_to_sign.append(hexFilePath)
    files_to_sign.append(codeBlockFilePath)

    for cal in calBlocks:
        files_to_sign.append(cal)

# --- Single Batch Signing Step ---
# All collected files are now signed in one command.
print(f"\n--- Initiating Batch Signing ---")
#print(files_to_sign)
signFilesBatch(files_to_sign, SCpin, tempDir)
print(f"--- Batch signing of {len(files_to_sign)} files requested. Now verifying results... ---")


# --- Verification and Post-Signing Edits ---
# First, verify that all signed files (_S.hex) were created successfully.
all_signed_files_created = [re.sub(".hex", "_S.hex", f) for f in files_to_sign]
for file_path in all_signed_files_created:
    checkSignedFile(file_path, tempDir)
print("All signed files have been verified successfully.")

print("\n--- Performing Post-Signing Edits ---")

if project == 1:
    # Now that all files are signed, perform the remaining edits on the signed versions.

    # 1. Patch the CRC of the SIGNED bootloader file.
    patchFile(signedHexPartPath, bootAddr)

    # 2. Export Block 0 from the SIGNED and patched bootloader.
    exportCode(signedHexPartPath, bootBlock0Addr)

    # 3. Merge the SIGNED bootloader into the SIGNED main hex file.
    mergeFile(signedHexFilePath, signedHexPartPath)

    # 4. Handle padding bytes if necessary.
    if paddingBytesEndAddr != "":
        # Adjust the end address to exclude padding bytes.
        codeExportAddr.patchEnd = str(hex(int(paddingBytesEndAddr, 16) - 1))

    # 5. Export the final code block (Block 0) from the merged and SIGNED hex file.
    exportCode(signedHexFilePath, codeExportAddr, signedCodeBlockFilePath)
else: # project == 2 (IB2/Rivian): files are already fully signed, no patch/merge/export needed
    # The CodeBlock still carries a trailing ECC/reserve section; strip it, leaving only the code block.
    removeEccBlock(signedCodeBlockFilePath)

print("Post-signing edits completed.")

# Create folder for signed files
signedDir = workingDir + "\\signed"
# If there is an old instance of it, delete it
if (os.path.exists(signedDir)):
    shutil.rmtree(signedDir)
os.mkdir(signedDir)

if project == 1:
    # Create array to store found CRCs
    crcStackFiles = []

    # Load files and CRCs into an array to cycle through and fill out csv
    crcStackFiles.append(savedCrc(os.path.relpath(signedHexPartPath, tempDir), captureCrc(signedHexPartPath, bootAddr.crcLoc)))
    crcStackFiles.append(savedCrc(os.path.relpath(signedCodeBlockFilePath, tempDir), captureCrc(signedCodeBlockFilePath, codeAddr.crcLoc)))
    for cal in signedCalBlocks:
        crcStackFiles.append(savedCrc(os.path.relpath(cal, tempDir), captureCrc(cal, calAddr.crcLoc)))

    # Create CSV, fill out CSVs
    crcCsvFile = open(signedDir + "\\crcList.csv", "w")
    for crcLine in crcStackFiles:
        crcCsvFile.write(crcLine.printCsv())

    crcCsvFile.close()
else: # project == 2: no CRC address exists for this chip, so an MD5 per file is used instead
    hashStackFiles = []

    if signedHexPartPath:
        hashStackFiles.append(savedMd5(os.path.relpath(signedHexPartPath, tempDir), computeMd5(signedHexPartPath)))
    hashStackFiles.append(savedMd5(os.path.relpath(signedHexFilePath, tempDir), computeMd5(signedHexFilePath)))
    hashStackFiles.append(savedMd5(os.path.relpath(signedCodeBlockFilePath, tempDir), computeMd5(signedCodeBlockFilePath)))
    for cal in signedCalBlocks:
        hashStackFiles.append(savedMd5(os.path.relpath(cal, tempDir), computeMd5(cal)))

    writeMd5ReportXlsx(signedDir + "\\crcList.xlsx", hashStackFiles)

print("CRC output file complete")

copySignedFiles(tempDir, signedDir)

# Removes temp directory when finished
if (os.path.exists(tempDir)):
    shutil.rmtree(tempDir)

print("Successfully Completed")

    