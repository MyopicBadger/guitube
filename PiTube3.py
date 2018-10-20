
import configparser
import copy
import io
import os

#!/usr/bin/env python
# import secrets # upgrade to this
import random
import re
import shlex
import string
import subprocess
import threading
import time
import uuid
import hashlib

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

from imgur_downloader import (
	ImgurDownloader
)  # https://github.com/jtara1/imgur_downloader

app = Flask(__name__)

downloadQueue = {}
folderView = {}
currentDownloadPercent = 0
currentDownloadUrl = ""
imgurAlbumSize = 0

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# The defaults below will be overwritten by the values in the #
# checkAndSetConfig() call, so don't go thinking changing	 #
# the values here will do anything useful					 #
youtubelocation = "."
dumbSaveFileName = "queue.temp"
jsonSaveFileName = "queue.json"
hostname = "0.0.0.0"
portnumber = 5001
debugmode = True
app_secret_key = "notEvenVaguelySecret"
downloadFormatString = "bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best"

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

savedDownloadQueueFile = os.path.join(
	os.path.dirname(os.path.abspath(__file__)), jsonSaveFileName
)
dumbSaveFile = os.path.join(
	os.path.dirname(os.path.abspath(__file__)), dumbSaveFileName
)
idCounter = 0
terminateFlag = 0
lastFilename = ""
download_thread = 0
configfile_name = "config.ini"


def checkAndSetConfig():
	global youtubelocation, dumbSaveFileName, jsonSaveFileName, hostname, portnumber, debugmode, app_secret_key
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
	return str(int(hashlib.md5(stringToHash.encode('utf-8')).hexdigest(), 16))

def saveDownloadQueue():
	global downloadQueue
	dumbSave()
	# for url in downloadQueue.keys():
	# 	downloadQueue[url]["id"] = "id_"+generateNewID()
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
	return redirect(url_for("mainPageFunction"))


def executeCommand(command):
	print(command)
	proc = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, bufsize=0)
	return str(proc.stdout.read())


class MyLogger(object):
	def debug(self, msg):
		pass

	def warning(self, msg):
		print(msg)

	def error(self, msg):
		print(msg)


def my_hook(d):
	global currentDownloadPercent
	global downloadQueue
	global lastFilename
	if d["status"] == "finished":
		print("Done downloading, now converting ...")
		os.utime(d.get("filename", ""))
	try:
		if lastFilename != d["key"]:
			iffyPrint(d, "filename")
		lastFilename = d["key"]
		print("lastFilename:" + lastFilename)
	except:
		pass

	if d["status"] == "downloading":
		currentDownloadPercent = (int(d.get("downloaded_bytes", 0)) * 100) / int(
			d.get("total_bytes", d.get("downloaded_bytes", 100))
		)
		downloadQueue[currentDownloadUrl]["filename"] = d.get("filename", "?")
		downloadQueue[currentDownloadUrl]["tbytes"] = d.get(
			"total_bytes", d.get("downloaded_bytes", 0)
		)
		downloadQueue[currentDownloadUrl]["dbytes"] = d.get("downloaded_bytes", 0)
		downloadQueue[currentDownloadUrl]["time"] = d.get("elapsed", "?")
		downloadQueue[currentDownloadUrl]["speed"] = d.get("speed", 0)
	downloadQueue[currentDownloadUrl]["canon"] = d.get("filename", currentDownloadUrl)
	downloadQueue[currentDownloadUrl]["status"] = d.get("status", "?")
	downloadQueue[currentDownloadUrl]["percent"] = currentDownloadPercent


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
	global download_thread
	global downloadQueue
	for url in downloadQueue.keys():
		if str(downloadQueue[url]["id"]) == id_num:
			if (
				downloadQueue[url]["status"] != "downloading"
				or downloadQueue[url]["status"] != "finished"
			):
				# flash("Removed " + getName(downloadQueue[url]), "info")
				del downloadQueue[url]
				saveDownloadQueue()
				return "OK"
	return "ERR"


@app.route("/youtube/retry/<id_num>")
def videoRestart(id_num):
	global download_thread
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
	global loopBreaker
	global terminateFlag
	loopBreaker = 10
	terminateFlag = 0
	fireDownloadThread()
	return "OK"


def fireDownloadThread():
	global download_thread
	if download_thread.is_alive():
		print("Thread already running")
	else:
		print("Thread starting")
		download_thread = threading.Thread(target=doDownload)
		download_thread.start()


@app.route("/youtube/add", methods=["POST", "GET"])
def videoAddProper():
	global idCounter
	if request.method == "POST":
		global download_thread
		global downloadQueue
		url = request.form["videourl"]
		for subURL in url.split():
			idCounter = idCounter + 1
			downloadQueue[subURL] = dict(
				[
					("status", "queued"),
					("url", subURL),
					("id", "id_" + generateNewID()),
					("mode", "video"),
				]
			)
			# flash("Added " + getName(downloadQueue[subURL]), "info")
		saveDownloadQueue()
		fireDownloadThread()
		return jsonify(downloadQueue)
	else:
		return jsonify(downloadQueue)


@app.route("/youtube/kill")
def shutdownAll():
	global terminateFlag
	global downloadQueue
	global loopBreaker
	loopBreaker = -1
	terminateFlag += 1
	saveDownloadQueue()
	# flash("Downloading will cease after current download finishes", "warn")
	download_thread._stop()
	shutdown_server()
	return redirect("/youtube", code=302)


@app.route("/youtube/removecompleted")
def removeFinished():
	global downloadQueue
	newDownloadQueue = copy.copy(downloadQueue)
	for url in downloadQueue.keys():
		if downloadQueue[url]["status"] == "completed":
			# flash("Removed " + getName(downloadQueue[url]), "info")
			del newDownloadQueue[url]
	downloadQueue = newDownloadQueue
	saveDownloadQueue()

	return "OK"


@app.route("/youtube/save")
def forceSave():
	global downloadQueue
	saveDownloadQueue()
	# flash("Saved " + str(os.path.abspath(savedDownloadQueueFile)), "info")
	return "OK"


@app.route("/youtube")
def videoList():
	global downloadQueue
	return render_template("vue.html")


def isPlayableFile(filename):
	for fname in os.listdir(youtubelocation):
		if fname.startswith(filename.split(".")[0]):
			fullpath = os.path.join(youtubelocation, fname)
			# print("FULL:" + fullpath)
			if os.path.isfile(fullpath):
				# print("MATCH: " + fname)
				if fullpath.endswith(".mp4") or fullpath.endswith(".webm"):
					return True
	return False


@app.route("/youtube/list.json")
def getAllFilesList():
	for fname in os.listdir(youtubelocation):
		if (isPlayableFile(fname)):
			folderView[fname] = dict(
				[
					("status", "completed"),
					("filename", fname),
					("canon", fname),
					("playable", isPlayableFile(fname)),
					("id", "id_" + generateHashID(fname)),
					("mode", "video"),
				]
			)
	return jsonify(dict(folderView))


@app.route("/youtube/video/playable/<filename>")
def queryVideo(filename):
	print(filename)
	return isPlayableFile(filename)


@app.route("/youtube/video/play/<filename>")
def serveVideo(filename):
	# print("Requested:" + filename)
	for fname in os.listdir(youtubelocation):
		print(fname)
		if fname.startswith(filename.split(".")[0]):
			fullpath = os.path.join(youtubelocation, fname)
			# print("FULL:" + fullpath)
			if os.path.isfile(fullpath):
				# print("MATCH: " + fname)
				# print("Sending: " + youtubelocation)
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


def getNextStartedItem():
	for url in downloadQueue.keys():
		if downloadQueue[url]["status"] == "downloading":
			return downloadQueue[url]
	return "NONE"


def getNextQueuedItem():
	saveDownloadQueue()
	nextItem = getNextStartedItem()
	if nextItem != "NONE":
		return nextItem
	for url in downloadQueue.keys():
		if downloadQueue[url]["status"] == "queued":
			return downloadQueue[url]
	return "NONE"


def getAllErrors():
	for url in downloadQueue.keys():
		if downloadQueue[url]["status"] == "queued":
			return False
	return True


def imgurOnDownloadHook(index, httpUrl, filepath):
	global currentDownloadPercent
	print(str(downloadQueue))
	print("Download Hook Fired for " + str(index))
	currentDownloadPercent = (int(index) * 100) / int(imgurAlbumSize)
	downloadQueue[currentDownloadUrl]["percent"] = currentDownloadPercent
	downloadQueue[currentDownloadUrl]["filename"] = filepath
	downloadQueue[currentDownloadUrl]["tbytes"] = imgurAlbumSize
	downloadQueue[currentDownloadUrl]["dbytes"] = index
	downloadQueue[currentDownloadUrl]["time"] = "?"
	downloadQueue[currentDownloadUrl]["speed"] = currentDownloadPercent
	downloadQueue[currentDownloadUrl]["canon"] = currentDownloadUrl
	downloadQueue[currentDownloadUrl]["status"] = "?"


loopBreaker = 10


def doDownload():
	global downloadQueue
	global currentDownloadUrl
	global loopBreaker
	global terminateFlag
	global imgurAlbumSize
	print(downloadFormatString)
	ydl_opts = {
		"logger": MyLogger(),
		"progress_hooks": [my_hook],
		"prefer_ffmpeg": True,
		"restrictfilenames": True,
		"format": downloadFormatString,
	}
	nextUrl = getNextQueuedItem()
	if nextUrl != "NONE":
		currentDownloadUrl = nextUrl["url"]
		print("proceeding to " + currentDownloadUrl)
		try:
			# there's a bug where this will error if your download folder is inside your application folder
			os.chdir(youtubelocation)
			match = re.match(
				"(https?)://(www\.)?(i\.|m\.)?imgur\.com/(a/|gallery/|r/)?/?(\w*)/?(\w*)(#[0-9]+)?(.\w*)?",  # NOQA
				currentDownloadUrl,
			)
			if match:
				downloadQueue[currentDownloadUrl]["status"] = "downloading"
				downloadQueue[currentDownloadUrl]["mode"] = "imgur"
				print("Matched Regex")
				downloader = ImgurDownloader(currentDownloadUrl, youtubelocation)
				print("Downloader created...")
				print("This albums has {} images".format(downloader.num_images()))
				imgurAlbumSize = downloader.num_images()
				downloader.on_image_download(imgurOnDownloadHook)

				resultsTuple = downloader.save_images()

				print("Saved!")
				print(resultsTuple)
				downloadQueue[currentDownloadUrl]["status"] = "completed"
			if not match:
				nextUrl["mode"] = "youtube"
				with youtube_dl.YoutubeDL(ydl_opts) as ydl:
					ydl.download([nextUrl["url"]])
				downloadQueue[nextUrl["url"]]["status"] = "completed"
				downloadQueue[nextUrl["url"]]["playable"] = queryVideo(
					downloadQueue[nextUrl["url"]]["filename"]
				)
				# os.chdir(os.path.expanduser("~"))
			os.chdir(os.path.dirname(os.path.realpath(__file__)))
			loopBreaker = 10
		except Exception as e:
			nextUrl["status"] = "error"
			nextUrl["error"] = e
			os.chdir(os.path.dirname(os.path.realpath(__file__)))
			# flash("Error " + str(e), "error")
		nextUrl = getNextQueuedItem()
		if nextUrl != "NONE" and loopBreaker > 0:
			loopBreaker = loopBreaker - 1
			print("loopBreaker:" + str(loopBreaker))
			if terminateFlag == 0:
				doDownload()
	else:
		print("Nothing to do - Finishing Process")


def shutdown_server():
	func = request.environ.get("werkzeug.server.shutdown")
	if func is None:
		raise RuntimeError("Not running with the Werkzeug Server")
	func()


download_thread = threading.Thread(target=doDownload)

if __name__ == "__main__":
	checkAndSetConfig()
	print("Working Directory: " + executeCommand("pwd"))
	print("Youtube-Dl Version: " + executeCommand("youtube-dl --version"))
	getDownloadQueue()
	app.secret_key = app_secret_key
	app.debug = debugmode
	app.auto_reload = debugmode
	app.run(host=hostname, port=portnumber)

