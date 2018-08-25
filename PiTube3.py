#!/usr/bin/env python
import copy
import json
import os
import shlex
import subprocess
import threading
import time
import configparser
import io

import youtube_dl
from flask import Flask, flash, redirect, render_template, request, url_for
from youtube_dl import DownloadError

app = Flask(__name__)

downloadQueue = {}
currentDownloadPercent = 0
currentDownloadUrl = ""
youtubelocation = "/"
dumbSaveFileName = "queue.temp"
jsonSaveFileName = "queue.json"
hostname = "0.0.0.0"
portnumber = 5002
debugmode = True
app_secret_key = "notEvenVaguelySecret"

savedDownloadQueueFile = os.path.join(
	os.path.dirname(os.path.abspath(__file__)), jsonSaveFileName
)
dumbSaveFile = os.path.join(os.path.dirname(os.path.abspath(__file__)), dumbSaveFileName)
idCounter = 0
terminateFlag = 0
lastFilename = ""
download_thread = 0
configfile_name = "config.ini"

def checkAndSetConfig():
	global youtubelocation, dumbSaveFileName, jsonSaveFileName, hostname, portnumber, debugmode, app_secret_key
	if not os.path.isfile(configfile_name):
	# Create the configuration file as it doesn't exist yet
		cfgfile = open(configfile_name, 'w')

		# Add content to the file
		Config = configparser.ConfigParser()
		Config.add_section('Downloader')
		Config.set('Downloader', 'download_folder', '/')
		Config.set('Downloader', 'download_queue', 'queue.json')
		Config.set('Downloader', 'dumb_download_queue', 'queue.temp')
		Config.add_section('Server')
		Config.set('Server','host','0.0.0.0')
		Config.set('Server','port', '5002')
		Config.set('Server','secret_key', str(os.urandom(24)))
		Config.set('Server','debug_mode', 'True')

		Config.write(cfgfile)
		cfgfile.close()
		checkAndSetConfig()
	else:
		parser = configparser.ConfigParser()
		parser.read(configfile_name)
		youtubelocation = parser.get('Downloader', 'download_folder')
		dumbSaveFileName = parser.get('Downloader', 'download_queue')
		jsonSaveFileName = parser.get('Downloader', 'dumb_download_queue')
		hostname = parser.get('Server', 'host')
		portnumber = parser.getint('Server', 'port')
		debugmode = parser.getboolean('Server', 'debug_mode')
		app_secret_key = parser.get('Server', 'secret_key')

def getDownloadQueue():
	global downloadQueue
	print("Loading: " + str(os.path.abspath(savedDownloadQueueFile)))
	try:
		with open(savedDownloadQueueFile) as f:
			json_data = f.read()
			downloadQueue = json.loads(json_data)
	except:
		downloadQueue = {}


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
				flash("Removed " + getName(downloadQueue[url]), "info")
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
	return redirect("/youtube", code=302)


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
				[("status", "queued"), ("url", subURL), ("id", "id_" + str(idCounter))]
			)
			flash("Added " + getName(downloadQueue[subURL]), "info")
		saveDownloadQueue()
		fireDownloadThread()
		return redirect("/youtube", code=302)
	else:
		return redirect("/youtube", code=302)


#@app.route("/youtube/list")
#def videoList1():
#	global downloadQueue
#	return render_template("filelist.html", queue=downloadQueue)


@app.route("/youtube/kill")
def shutdownAll():
	global terminateFlag
	global downloadQueue
	global loopBreaker
	loopBreaker = -1
	terminateFlag += 1
	saveDownloadQueue()
	flash("Downloading will cease after current download finishes", "warn")
	return redirect("/youtube", code=302)


@app.route("/youtube/removecompleted")
def removeFinished():
	global downloadQueue
	newDownloadQueue = copy.copy(downloadQueue)
	for url in downloadQueue.keys():
		if downloadQueue[url]["status"] == "completed":
			flash("Removed " + getName(downloadQueue[url]), "info")
			del newDownloadQueue[url]
	downloadQueue = newDownloadQueue
	saveDownloadQueue()

	return redirect("/youtube", code=302)


@app.route("/youtube/save")
def forceSave():
	global downloadQueue
	saveDownloadQueue()
	flash("Saved " + str(os.path.abspath(savedDownloadQueueFile)), "info")
	return redirect("/youtube", code=302)


@app.route("/youtube")
def videoList():
	global downloadQueue
	return render_template("progress.html", queue=downloadQueue, added="NONE")


@app.route("/youtube/queue")
def videoMainQueue():
	global downloadQueue
	return render_template("mainqueue.html", queue=downloadQueue, added="NONE")


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


loopBreaker = 10


def doDownload():
	global downloadQueue
	global currentDownloadUrl
	global loopBreaker
	global terminateFlag
	ydl_opts = {
		"logger": MyLogger(),
		"progress_hooks": [my_hook],
		"prefer_ffmpeg": True,
		"restrictfilenames": True,
	}
	nextUrl = getNextQueuedItem()
	if nextUrl != "NONE":
		currentDownloadUrl = nextUrl["url"]
		print("proceeding to " + currentDownloadUrl)
		try:
			os.chdir(youtubelocation)
			with youtube_dl.YoutubeDL(ydl_opts) as ydl:
				ydl.download([nextUrl["url"]])
			downloadQueue[nextUrl["url"]]["status"] = "completed"
			os.chdir(os.path.expanduser("~"))
			loopBreaker = 10
		except Exception as e:
			nextUrl["status"] = "error"
			nextUrl["error"] = e
			os.chdir(os.path.expanduser("~"))
			flash("Error " + str(e), "error")
		nextUrl = getNextQueuedItem()
		if nextUrl != "NONE" and loopBreaker > 0:
			loopBreaker = loopBreaker - 1
			print("loopBreaker:" + str(loopBreaker))
			if terminateFlag == 0:
				doDownload()
	else:
		print("Nothing to do - Finishing Process")


download_thread = threading.Thread(target=doDownload)

if __name__ == "__main__":
	checkAndSetConfig()
	print("Working Directory: " + executeCommand("pwd"))
	print("Youtube-Dl Version: " + executeCommand("youtube-dl --version"))
	getDownloadQueue()
	app.secret_key = app_secret_key
	app.debug = debugmode
	app.run(host=hostname, port=portnumber)

