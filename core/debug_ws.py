with open(r'd:\Kursus with coderNTT\CANI\viquam\core\karyawan_views.py', 'rb') as f:
    lines = f.readlines()
    for i in range(455, 460): # lines 456-460
        print(f"Line {i+1}: {lines[i]!r}")
