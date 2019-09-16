import os
import json


def getDirectoryTree(folder):
    # param folder: 文件目录
    # return:目录的字典
    dirtree = {'children': []}
    if os.path.isdir(folder):
        basename = os.path.basename(folder)
        dirtree['name'] = basename
        for item in os.listdir(folder):
            if os.path.isdir(os.path.join(folder, item)):
                dirtree['children'].append(getDirectoryTree(os.path.join(folder, item)))
        return dirtree


def getDirectoryTreeWithJson(folder):
    # 将文件夹生成树状的json串
    # param folder: 文件夹
    # return:文件树json
    return json.dumps(getDirectoryTree(folder))


if __name__ == '__main__':
    dirs = getDirectoryTreeWithJson('video')
    print(dirs)
