import os
import glob


def fun(path, parent):
    global Id
    global jsonstr
    global count

    for i, fn in enumerate(glob.glob(path + os.sep + '*')):

        if os.path.isdir(fn):
            jsonstr += '''{"id":"''' + str(Id) + '''","parent":"''' + str(
                parent) + '''","name":"''' + os.path.basename(fn) + '''","children":['''
            parent = Id
            Id += 1
            for j, li in enumerate(glob.glob(fn + os.sep + '*')):
                if os.path.isdir(li):
                    jsonstr += '''{"id":"''' + str(Id) + '''","parent":"''' + str(
                        parent) + '''","name":"''' + os.path.basename(
                        li) + '''","children":['''
                    parent = Id
                    Id += 1
                    fun(li, parent)
                    jsonstr += "]}"
                    if j < len(glob.glob(fn + os.sep + '*')) - 1:
                        jsonstr += ","
            jsonstr += "]}"
            if i < len(glob.glob(path + os.sep + '*')) - 1:
                jsonstr += ","
    return jsonstr


path = "video"
parent = 0
Id = 0
jsonstr = "["
jsonstr = fun(path, 0)
jsonstr += "]"
print(jsonstr)

