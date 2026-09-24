import json, os, zipfile

f = "/tmp/files/cm_bp_test.xlsx"
if not os.path.exists(f):
    print("File not found")
    exit()

size = os.path.getsize(f)
print(f"File size: {size} bytes")

try:
    with zipfile.ZipFile(f, 'r') as z:
        namelist = z.namelist()
        print(f"Valid xlsx/zip, entries: {len(namelist)}")
        for name in namelist:
            if 'sheet' in name.lower() or 'sharedStrings' in name:
                data = z.read(name)
                print(f"  {name}: {len(data)} bytes")
                if len(data) < 2000 and b'xml' in data[:100]:
                    print(f"    Content preview: {data[:500]}")
except zipfile.BadZipFile:
    with open(f, 'rb') as fh:
        header = fh.read(200)
    print(f"Not a valid zip/xlsx. Header: {header[:100]}")
    try:
        text = open(f).read(500)
        print(f"Text content: {text}")
    except:
        pass
