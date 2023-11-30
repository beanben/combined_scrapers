try:
    file = open("log.txt", "r+")
    file.truncate(0)
    file.close()
except:
    pass
