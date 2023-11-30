import glob
import datetime

current_date = datetime.datetime.today().strftime("%Y%m%d")
files = [file for file in glob.glob("./output/*.csv") if current_date in file]

try:
    for path in files:
        file = open(path, "r+")
        file.truncate(0)
        file.close()
except:
    pass
