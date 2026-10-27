# -*- coding: utf-8 -*-
"""
Created on Thu Jan 5 2023
Updated on Mon Sep 2 2026
@author: MEW1PLY, RUM3PLY, BES6FH 

Tool to automate CRC patching and software signing process of D4 Tesla Software Releases
Created by: Wegienka Maxwell (CC/ECE1-NA)
Updated by: LRO1GA, GLE2GA
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
class savedCrcMd5:
    fileName: str # File name the CRC/hash was computed from
    crc: str # Real "App Info CRC" read from the file (None if not applicable, e.g. bootloader)
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

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# IB2/Project 2 real CRC extraction - ported from FinalizeRelease_V12.xlsm's VBA macro
# (process.bas: getGeneration/getcrc/readAtAddress/motToIntel), validated byte-exact against
# real release examples. The CRC is baked into the firmware image at build time and is only
# ever READ, never patched, for this chip family.
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def _ib2VbInstr(s: str, substr: str, start: int = 1):
    # Mirrors VBA's 1-based InStr(start, string, substring)
    idx = s.find(substr, start - 1)
    return idx + 1 if idx >= 0 else 0

def _ib2VbMid(s: str, start: int, length: int = None):
    # Mirrors VBA's 1-based Mid(string, start[, length])
    if start < 1:
        start = 1
    if length is None:
        return s[start - 1:]
    return s[start - 1:start - 1 + length]

def _ib2GetGeneration(hexText: str):
    # Mirrors VBA's getGeneration(): identifies the hexfile's build generation from fixed markers
    if _ib2VbInstr(hexText, ":020000040000FA") == 1 and 0 < _ib2VbInstr(hexText, ":20") < 20:
        genId = _ib2VbInstr(hexText, ":20100000") + 2 + 9
        generation = 1
    else:
        genId = 16 + 11 + 2
        generation = 0
    if _ib2VbMid(hexText, genId, 6) in ("52454C", "53544D"):
        generation += 930
    pos10 = _ib2VbInstr(hexText, ":10", 9)
    if 0 < pos10 < 20:
        pos = _ib2VbInstr(hexText, ":", 2 * (11 + 2 * 16)) + 9 + 24
        val = _ib2VbMid(hexText, pos, 4)
        if val == "804C":
            generation = 92
        if val == "802A":
            generation = 91
    return generation

def _ib2MotToIntel(adr: str):
    # Mirrors VBA's motToIntel(): reverses byte order of a hex-digit-pair string
    result = ""
    ln = len(adr)
    while ln > 0:
        result += adr[ln - 2:ln]
        ln -= 2
    return result

# readAtAddress ignores its own "gen" parameter in the real VBA macro and instead relies on
# the module-level "generation" global set by the caller - this quirk must be replicated exactly
_ib2Generation = 0

def _ib2ReadAtAddress(hexText: str, adr: str, length: int):
    # Mirrors VBA's readAtAddress(): reads `length` bytes starting at the given address,
    # locating the right extended-linear-address record/data-record pair by text search
    if len(adr) < 8:
        adr = adr.rjust(8, "0")
    aSect = _ib2VbMid(adr, 1, 4)
    if _ib2Generation in (930, 931):
        lln = ":20"
        div = 32
    else:
        lln = ":10"
        div = 16
    aAdr = _ib2VbMid(adr, 5, 4)
    adC = int(aAdr, 16) // div
    ad = adC * div
    hexad = format(ad, "X")
    adrSeg = hexad[-4:] if len(hexad) >= 4 else hexad
    offset = int(aAdr, 16) - int(adrSeg, 16)
    sectorStart = _ib2VbInstr(hexText, ":02000004" + aSect) + 9
    valPoi = _ib2VbInstr(hexText, lln + adrSeg, sectorStart) + 9 + offset * 2
    result = ""
    pos = valPoi
    for _ in range(length):
        if ":" in _ib2VbMid(hexText, pos, 5):
            pos = pos + 9 + 2 + 2
        result += _ib2VbMid(hexText, pos, 2)
        pos += 2
    if _ib2Generation in (930, 931):
        result = _ib2MotToIntel(result)
    return result

def _ib2GetCrc(hexText: str, generation: int):
    # Mirrors VBA's getcrc(): follows the "CHECK structure" pointer embedded in the image
    global _ib2Generation
    _ib2Generation = generation

    if generation == 931:
        chkref = _ib2VbMid(hexText, _ib2VbInstr(hexText, ":201000") + 7 + 2 + 2 * 0x10, 8)
    elif generation == 930:
        chkref = _ib2VbMid(hexText, _ib2VbInstr(hexText, ":20") + 9 + 0x10 * 2, 8)
    else:
        chkref = None

    if generation in (930, 931):
        chkref = _ib2MotToIntel(chkref)
        chkSegAddr = format(int(chkref, 16) + 2, "X").rjust(8, "0")
        chkSegmentation = _ib2ReadAtAddress(hexText, chkSegAddr, 1)
        longAdr = int(chkref, 16) + 0x10 - 8
        crcAddr = format(longAdr, "X").rjust(8, "0")
        crc = _ib2ReadAtAddress(hexText, crcAddr, 8)
        if int(chkSegmentation, 16) == 1:
            crc2 = int(crc[0:8], 16)
            crc1 = int(crc[8:16], 16)
            crc = format(crc1 ^ crc2, "X")
        else:
            crc = crc[8:16]
    elif generation in (91, 92):
        chkref = _ib2VbMid(hexText, _ib2VbInstr(hexText, ":", 2 * (11 + 3 * 16)) + 9 + 8, 8)
        longAdr = int(chkref, 16) + 8
        crcAddr = format(longAdr, "X").rjust(8, "0")
        crc = _ib2ReadAtAddress(hexText, crcAddr, 8)
    else:
        return None

    return crc.rjust(8, "0")[-8:]

def computeIb2Crc(inFile: str):
    """
    Reads the real "App Info CRC" baked into an IB2/project 2 hex file at build time.

    Parameters:
        inFile: Signed hex file to read the CRC from

    Returns:
        "0xXXXXXXXX" formatted CRC string, or None if this file type carries no CRC
        (e.g. the bootloader HexPart, which the real release documentation also leaves blank)
    """

    # newline="" preserves \r\n as 2 literal characters, matching VBA's raw-string file read
    with open(inFile, "r", encoding="ascii", errors="ignore", newline="") as f:
        hexText = f.read()

    generation = _ib2GetGeneration(hexText)
    if generation not in (930, 931, 91, 92):
        return None

    crc = _ib2GetCrc(hexText, generation)
    return ("0x" + crc) if crc else None

def writeCrcMd5ReportXlsx(reportPath: str, hashRows: list):
    """
    Writes a minimal .xlsx workbook (File, CRC, MD5 columns) built directly as OOXML,
    mirroring the release report format produced by Gen9_Sign_release_tool_CLI.py while
    adding the real App Info CRC alongside the MD5, similar to the official
    Bosch_Release_Documentation_*.xlsm layout.

    Parameters:
        reportPath: Full path of the .xlsx file to create
        hashRows: List of savedCrcMd5 entries to write, one per row

    Returns:
        N/A
    """

    sheetRows = [["File", "CRC", "MD5"]] + [[row.fileName, row.crc or "", row.md5] for row in hashRows]

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

def selectIb2Variant(candidates: list):
    """
    Finds project 2's (IB2/Rivian) bootloader HexPart automatically based on whether the
    release is a Legacy or Europium (Everest/Highland) project, rather than asking the
    operator to pick blindly from a list of candidates.

    Parameters:
        candidates: PRJ_HexPart_*.hex file paths found in the extracted container

    Returns:
        Selected bootloader file path, or None if this is a Legacy release (no bootloader)
    """

    sel = 0
    while not sel:
        try:
            sel = int(input('Enter 1 if this is a Legacy IB2 project or 2 if this is a Europium (Everest/Highland) IB2 project: '))
            if sel not in (1, 2):
                raise ValueError
        except ValueError:
            sel = 0
            print("Invalid option entered!")

    if sel == 1:
        # Legacy releases don't ship a bootloader HexPart at all
        return None

    # Europium releases ship exactly one bootloader HexPart, named after its chip variant
    hexPartPath = next((c for c in candidates if "EverestBldr" in c or "HighlandBldr" in c), None)
    if hexPartPath is None:
        sys.exit("Europium project selected, but no HexPart containing 'EverestBldr' or 'HighlandBldr' was found")

    return hexPartPath

def hexOrApplCont():
    sel = 0
    while not sel:
        try: 
            sel = int(input('Enter 1 to prepare from an ApplContainer only, 2 to prepare from PRJ_HEX from PMSE, or 3 to process a BLU Hexfile: '))
            if sel not in (1, 2, 3):
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

if choice == 3:
    # BLU Hexfile: a single standalone hexfile that gets signed and then CRC-patched
    # (same CS9/Hexview mechanism as ESP project preparation), independent of the
    # ApplContainer/PRJ_HEX flows below.
    print("Opening the BLU Hexfile")
    fname = getOpenFileName("Open BLU Hexfile", ".hex", "*.hex", os.environ["temp"])
    fname = re.sub("\0", "", fname)

    workingDir = os.path.dirname(fname)
    tempDir = workingDir + "\\temp"
    if os.path.exists(tempDir):
        shutil.rmtree(tempDir)
    os.mkdir(tempDir)

    bluHexPath = tempDir + "\\" + os.path.basename(fname)
    shutil.copy(fname, bluHexPath)

    print("Opening the Map File")
    mapFname = getOpenFileName("Open Map File", ".map", "Map_*.map", os.environ["temp"])
    mapFname = re.sub("\0", "", mapFname)

    codeAddr, calAddr, paddingBytesEndAddr = fetchCodeCalAddr(mapFname)

    SCpin = ""
    while True:
        SCpin = getpass.getpass("Please enter smart card PIN (Input not shown): ")
        try:
            int(SCpin)
            break
        except ValueError:
            print("Invalid entry, PIN cannot contain letters")

    print("Signing the BLU Hexfile...")
    signFile(bluHexPath, SCpin)
    signedBluHexPath = re.sub(".hex", "_S.hex", bluHexPath)
    checkSignedFile(signedBluHexPath, tempDir)

    print("Patching CRC into the signed BLU Hexfile...")
    patchFile(signedBluHexPath, codeAddr)

    # Rename to mark this as a processed BLU Hexfile rather than a regular HexPart
    finalBluPath = re.sub("HexPart", "BLUPart", signedBluHexPath)
    if finalBluPath != signedBluHexPath:
        shutil.move(signedBluHexPath, finalBluPath)
        signedBluHexPath = finalBluPath

    signedDir = workingDir + "\\signed"
    if os.path.exists(signedDir):
        shutil.rmtree(signedDir)
    os.mkdir(signedDir)
    shutil.copy(signedBluHexPath, signedDir + "\\" + os.path.basename(signedBluHexPath))

    if os.path.exists(tempDir):
        shutil.rmtree(tempDir)

    print("Successfully Completed")
    sys.exit(0)

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

# Project 2's bootloader HexPart (if any) is picked automatically based on Legacy/Europium
if project == 2:
    hexPartPath = selectIb2Variant(hexPartCandidates)

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
    # CodeBlock, Hexfile, and HexPart all carry a trailing ECC/reserve section; strip it from each.
    removeEccBlock(signedCodeBlockFilePath)
    removeEccBlock(signedHexFilePath)
    if signedHexPartPath:
        removeEccBlock(signedHexPartPath)

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
else: # project == 2 (IB2/Rivian): the CRC is a value baked into the image at build time, read it directly
    hashStackFiles = []

    if signedHexPartPath:
        hashStackFiles.append(savedCrcMd5(os.path.relpath(signedHexPartPath, tempDir), computeIb2Crc(signedHexPartPath), computeMd5(signedHexPartPath)))
    hashStackFiles.append(savedCrcMd5(os.path.relpath(signedHexFilePath, tempDir), computeIb2Crc(signedHexFilePath), computeMd5(signedHexFilePath)))
    hashStackFiles.append(savedCrcMd5(os.path.relpath(signedCodeBlockFilePath, tempDir), computeIb2Crc(signedCodeBlockFilePath), computeMd5(signedCodeBlockFilePath)))
    for cal in signedCalBlocks:
        hashStackFiles.append(savedCrcMd5(os.path.relpath(cal, tempDir), computeIb2Crc(cal), computeMd5(cal)))

    writeCrcMd5ReportXlsx(signedDir + "\\crcList.xlsx", hashStackFiles)

print("CRC output file complete")

copySignedFiles(tempDir, signedDir)

# Removes temp directory when finished
if (os.path.exists(tempDir)):
    shutil.rmtree(tempDir)

print("Successfully Completed")

    