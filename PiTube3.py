# !/usr/bin/env python
# import secrets # upgrade to this
# -*- coding: UTF-8 -*-
import configparser
import copy
import io
import os

import random
import re
import shlex
import string
import subprocess
import threading
import time
import uuid
import hashlib
import glob

import youtube_dl
from flask import (
    Flask,
    Response,
    flash,
    json,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from youtube_dl import DownloadError
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

downloadQueue = {}
folderView = {}
lastFileList = ""
currentDownloadPercent = 0
currentDownloadUrl = ""
imgurAlbumSize = 0
folderQueue = {}

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# The defaults below will be overwritten by the values in the #
# checkAndSetConfig() call, so don't go thinking changing	 #
# the values here will do anything useful					 #
youtubelocation = "."
dumbSaveFileName = "queue.temp"
jsonSaveFileName = "queue.json"
hostname = "127.0.0.1"
portnumber = 5000
debugmode = True
app_secret_key = "notEvenVaguelySecret"
downloadFormatString = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
os_string = "Linux"

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

savedDownloadQueueFile = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), jsonSaveFileName
)
dumbSaveFile = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), dumbSaveFileName
)
idCounter = 0
terminateFlag = 0
configfile_name = "config.ini"
commandMapping = {"ls -1": "Get-ChildItem -Name", "pwd": "Get-Location"}
downloadThreadSize = 5


def getCommand(commandString):
    if os_string == "Linux":
        return commandString
    else:
        if commandString in commandMapping:
            return commandMapping[commandString]
        else:
            return commandString


def checkAndSetConfig():
    global youtubelocation, dumbSaveFileName, jsonSaveFileName, hostname, portnumber, debugmode, app_secret_key, downloadFormatString, os_string
    if not os.path.isfile(configfile_name):
        # Create the configuration file as it doesn't exist yet
        cfgfile = open(configfile_name, "w")

        # Generate a suitable secret key (so 32 random characters)
        alphabet = string.ascii_letters + string.digits
        password = "".join(random.choice(alphabet) for i in range(32))

        # Add content to the file
        Config = configparser.ConfigParser()
        Config.add_section("Downloader")
        Config.set("Downloader", "download_folder", ".")
        Config.set("Downloader", "download_queue", "queue.json")
        Config.set("Downloader", "dumb_download_queue", "queue.temp")
        Config.set(
            "Downloader",
            "download_format_string",
            "bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        )
        Config.add_section("Server")
        Config.set("Server", "host", "0.0.0.0")
        Config.set("Server", "port", "5002")
        Config.set("Server", "secret_key", password)
        Config.set("Server", "debug_mode", "False")
        Config.set("Server", "os_string", "Linux")

        Config.write(cfgfile)
        cfgfile.close()
        checkAndSetConfig()
    else:
        parser = configparser.ConfigParser()
        parser.read(configfile_name)
        youtubelocation = parser.get("Downloader", "download_folder")
        dumbSaveFileName = parser.get("Downloader", "download_queue")
        jsonSaveFileName = parser.get("Downloader", "dumb_download_queue")
        downloadFormatString = parser.get("Downloader", "download_format_string")
        hostname = parser.get("Server", "host")
        portnumber = parser.getint("Server", "port")
        debugmode = parser.getboolean("Server", "debug_mode")
        app_secret_key = parser.get("Server", "secret_key")
        os_string = parser.get("Server", "os_string")


def getDownloadQueue():
    global downloadQueue
    print("Loading: " + str(os.path.abspath(savedDownloadQueueFile)))
    try:
        with open(savedDownloadQueueFile) as f:
            json_data = f.read()
            downloadQueue = json.loads(json_data)
    except:
        downloadQueue = {}


def generateNewID():
    newID = str(uuid.uuid4())
    print("New ID: " + newID)
    return newID


def generateHashID(stringToHash):
    return str(int(hashlib.md5(stringToHash.encode("utf-8")).hexdigest(), 16))


def saveDownloadQueue():
    global downloadQueue
    dumbSave()
    try:
        with open(savedDownloadQueueFile, "w") as savefile:
            print("Saving: " + str(os.path.abspath(savedDownloadQueueFile)))
            print(json.dumps(downloadQueue, ensure_ascii=False), file=savefile)

    except TypeError:
        for url in downloadQueue.keys():
            downloadQueue[url]["status"] == str(downloadQueue[url]["status"])


def dumbSave():
    with open(dumbSaveFile, "w") as savefile2:
        for url in downloadQueue.keys():
            print(url, file=savefile2)


@app.route("/")
def rootRedirect():
    return redirect(url_for("videoList"))


def executeCommand(command):
    print("On os: " + os_string)
    command = getCommand(command)
    print(command)
    proc = subprocess.Popen(
        shlex.split(command), stdout=subprocess.PIPE, bufsize=0, shell=True
    )
    return str(proc.stdout.read())


class MyLogger(object):
    def debug(self, msg):
        pass

    def warning(self, msg):
        print(msg)

    def error(self, msg):
        print(msg)


class MyHook:
    def __init__(self, tid):
        self.tid = tid

    def hook(self, d):
        global currentDownloadPercent
        global downloadQueue
        for url in downloadQueue.keys():
            if str(downloadQueue[url]["id"]) == self.tid:

                if d["status"] == "finished":
                    print("Done downloading, now converting ...")
                    os.utime(d.get("filename", ""))

                if d["status"] == "downloading":
                    currentDownloadPercent = (int(d.get("downloaded_bytes", 0)) * 100) / int(
                        d.get("total_bytes", d.get("downloaded_bytes", 100))
                    )
                    downloadQueue[url]["filename"] = d.get("filename", "?")
                    downloadQueue[url]["tbytes"] = d.get(
                        "total_bytes", d.get("downloaded_bytes", 0)
                    )
                    downloadQueue[url]["dbytes"] = d.get("downloaded_bytes", 0)
                    downloadQueue[url]["time"] = d.get("elapsed", "?")
                    downloadQueue[url]["speed"] = d.get("speed", 0)
                downloadQueue[url]["canon"] = d.get("filename", url)
                downloadQueue[url]["status"] = d.get("status", "?")
                downloadQueue[url]["percent"] = currentDownloadPercent


def iffyPrint(d, key):
    if key in d:
        print(str(key) + ": " + str(d[key]))


def getName(theObject):
    try:
        return theObject["filename"]
    except:
        return theObject["url"]


@app.route("/youtube/version")
def getVersion():
    return executeCommand("youtube-dl --version")


@app.route("/youtube/remove/<id_num>")
def videoRemove(id_num):
    global downloadQueue
    for url in downloadQueue.keys():
        if str(downloadQueue[url]["id"]) == id_num:
            if (
                    downloadQueue[url]["status"] != "downloading"
                    or downloadQueue[url]["status"] != "finished"
            ):
                del downloadQueue[url]
                saveDownloadQueue()
                return "OK"
    return "ERR"


@app.route("/youtube/retry/<id_num>")
def videoRestart(id_num):
    global downloadQueue
    for url in downloadQueue.keys():
        if downloadQueue[url]["id"] == id_num:
            if (
                    downloadQueue[url]["status"] != "downloading"
                    or downloadQueue[url]["status"] != "finished"
            ):
                downloadQueue[url]["status"] = "queued"
                fireDownloadThread()
                return "OK"
    return "ERR"


@app.route("/youtube/resume")
def forceStart():
    global terminateFlag
    terminateFlag = 0
    fireDownloadThread()
    return "OK"


def fireDownloadThread():
    executor.submit(doDownload())


@app.route("/youtube/add", methods=["POST", "GET"])
def videoAddProper():
    global idCounter
    if request.method == "POST":
        global downloadQueue
        url = request.form["videourl"]
        path = request.form["videoPaths"]
        name = request.form["videoNames"]
        for subURL in url.split():
            idCounter = idCounter + 1
            downloadQueue[subURL] = dict(
                [
                    ("status", "queued"),
                    ("url", subURL),
                    ("id", "id_" + generateNewID()),
                    ("mode", "video"),
                    ("path", path),
                    ("name", name)
                ]
            )
        saveDownloadQueue()
        fireDownloadThread()
        return jsonify(downloadQueue)
    else:
        return jsonify(downloadQueue)


@app.route("/youtube/kill")
def shutdownAll():
    global terminateFlag
    global downloadQueue
    terminateFlag += 1
    saveDownloadQueue()
    shutdown_server()
    return redirect("/youtube", code=302)


@app.route("/youtube/removecompleted")
def removeFinished():
    global downloadQueue
    newDownloadQueue = copy.copy(downloadQueue)
    for url in downloadQueue.keys():
        if downloadQueue[url]["status"] == "completed":
            del newDownloadQueue[url]
    downloadQueue = newDownloadQueue
    saveDownloadQueue()

    return "OK"


@app.route("/youtube/save")
def forceSave():
    global downloadQueue
    saveDownloadQueue()
    return "OK"


@app.route("/youtube")
def videoList():
    global downloadQueue
    return render_template("vue.html")


@app.route("/youtube/selectfolder")
def selectFolder():
    return render_template("SelectFolder.html")


def isPlayableFile(filename):
    for fname in os.listdir(youtubelocation):
        if fname.startswith(filename.split(".")[0]):
            fullpath = fname
            if os.path.isfile(fullpath):
                if fullpath.endswith(".mp4") or fullpath.endswith(".webm"):
                    return True
    return False


@app.route("/youtube/list.json")
def getAllFilesList():
    global lastFileList
    start = time.time()
    fileList = glob.glob(youtubelocation + "*")
    if fileList != lastFileList:
        lastFileList = fileList
        for fpath in fileList:
            fname = os.path.basename(fpath)
            if fname.endswith(".mp4") or fname.endswith(".webm"):
                folderView[fname] = dict(
                    [
                        ("status", "completed"),
                        ("filename", fname),
                        ("canon", fname),
                        ("playable", True),
                        ("id", "id_" + fname),
                        ("mode", "video"),
                    ]
                )
    end = time.time()
    print("list speed: " + str(end - start) + "s")
    return jsonify(dict(folderView))


@app.route("/youtube/video/playable/<filename>")
def queryVideo(filename):
    print(filename)
    return isPlayableFile(filename)


@app.route("/youtube/video/play/<filename>")
def serveVideo(filename):
    for fname in os.listdir(youtubelocation):
        print(fname)
        if fname.startswith(filename.split(".")[0]):
            fullpath = os.path.join(youtubelocation, fname)
            if os.path.isfile(fullpath):
                # return send_from_directory(youtubelocation, fullpath, as_attachment=False)
                # return send_file(fullpath, mimetype=fullpath)
                g = open(fullpath, "rb")  # or any generator
                return Response(g, direct_passthrough=True)


@app.route("/youtube/queue.json")
def videoJSONQueue():
    global downloadQueue
    # Manually stringify the error object if there is one,
    # because apparently jsonify can't do it automatically
    for url in downloadQueue.keys():
        if downloadQueue[url]["status"] == "error":
            downloadQueue[url]["error"] = str(downloadQueue[url]["error"])
    return jsonify(dict(downloadQueue))


@app.route("/youtube/percent")
def videoCurrentPercent():
    global downloadQueue
    print("/youtube/percent " + str(currentDownloadPercent))
    return str(currentDownloadPercent)


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


parent = 0
Id = 0
jsonstr = "["


@app.route("/youtube/getfolder", methods=["POST"])
def getFolder():
    if request.method == "POST":
        global folderQueue
        folderName = request.form["folderName"]
        global jsonstr
        global parent
        global Id
        parent = 0
        Id = 0
        jsonstr = "["
        jsonstr = fun(folderName, 0)
        jsonstr += "]"
        return jsonstr


def getNextStartedItem():
    for url in downloadQueue.keys():
        if downloadQueue[url]["status"] == "downloading":
            return downloadQueue[url]
    return "NONE"


def getNextQueuedItem():
    saveDownloadQueue()
    # nextItem = getNextStartedItem()
    # if nextItem != "NONE":
    #     return nextItem
    for url in downloadQueue.keys():
        if downloadQueue[url]["status"] == "queued":
            return downloadQueue[url]
    return "NONE"


def getAllErrors():
    for url in downloadQueue.keys():
        if downloadQueue[url]["status"] == "queued":
            return False
    return True


def doDownload():
    global downloadQueue
    global currentDownloadUrl
    global terminateFlag
    global imgurAlbumSize
    print(downloadFormatString)
    nextUrl = getNextQueuedItem()
    if nextUrl != "NONE":
        ydl_opts = {
            "logger": MyLogger(),
            "progress_hooks": [MyHook(downloadQueue[nextUrl["url"]]["id"]).hook],
            "prefer_ffmpeg": True,
            "restrictfilenames": False,
            "format": downloadFormatString,
            "outtmpl": ""
        }
        currentDownloadUrl = nextUrl["url"]
        path = nextUrl["path"]
        name = nextUrl["name"]
        if name != "NONE" and name != "":
            ydl_opts['outtmpl'] = path + name
        else:
            ydl_opts['outtmpl'] = path + '%(title)s-%(id)s.%(ext)s'
        print("proceeding to " + currentDownloadUrl)
        try:
            # there's a bug where this will error if your download folder is inside your application folder
            os.chdir(youtubelocation)
            nextUrl["mode"] = "youtube"
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([nextUrl["url"]])
            downloadQueue[nextUrl["url"]]["status"] = "completed"
            downloadQueue[nextUrl["url"]]["playable"] = queryVideo(
                downloadQueue[nextUrl["url"]]["filename"]
            )
            os.chdir(os.path.dirname(os.path.realpath(__file__)))
        except Exception as e:
            nextUrl["status"] = "error"
            nextUrl["error"] = e
            os.chdir(os.path.dirname(os.path.realpath(__file__)))
        nextUrl = getNextQueuedItem()
        if nextUrl != "NONE":
            if terminateFlag == 0:
                doDownload()
    else:
        print("Nothing to do - Finishing Process")


def shutdown_server():
    func = request.environ.get("werkzeug.server.shutdown")
    if func is None:
        raise RuntimeError("Not running with the Werkzeug Server")
    func()


executor = ThreadPoolExecutor(max_workers=downloadThreadSize)

if __name__ == "__main__":
    checkAndSetConfig()
    print("Working Directory: " + executeCommand("pwd"))
    print("Youtube-Dl Version: " + executeCommand("youtube-dl --version"))
    getDownloadQueue()
    app.secret_key = app_secret_key
    app.debug = debugmode
    app.auto_reload = debugmode
    app.run(host=hostname, port=portnumber)
