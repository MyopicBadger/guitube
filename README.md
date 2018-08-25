# guitube
A simple web frontend for youtube-dl

![alt text](https://github.com/MyopicBadger/guitube/raw/master/doc/example.png "Guitube in action")

Formerly known (to me at least) as PiTube, because it started as a program I wrote to run on a RaspberryPi.

## Getting started

Before you can use guitube, you'll need to install Python 3, Flask and youtube-dl.

You can install python from [Python.org](https://www.python.org/)

That will also install pip, a python package management tool. You can use that to install flask and youtube-dl by running the following command:

```
pip install Flask
pip install youtube-dl
```

Then just run `python3 PiTube3.py` to start the server.

The webpage it serves will be accessible via your browser, on localhost:5002 (configurable in the config file)

On first run, the program will create a config.ini file. This contains all the settings for the application

## config.ini

The .ini file contains the two sections, 'Downloader' and 'Server':

#### Downloader
`download_folder` - The folder that downloaded files are downloaded to. This needs to exist or downloads will fail.
`download_queue` - The file that the current download queue will be saved to. This is used to persist the queue between restarts of the application. This will be created if it doesn't exist, so you can delete it to delete the queue if you want, although you could just delete them on the page instead.
`dumb_download_queue` - Ignore this, it's dumb.

#### Server

Server settings are configuration passed through to the built in Flask server

`host` - When set to 0.0.0.0, the hosted pages will be visible to other users on the network. When set to 127.0.0.1 they will only be visible on the computer running the application.
`port` - The port number that the server will be accessible using.
`secret_key` - The secret key used to encrypt secure session cookies. It doesn't really matter what this is, as long as it's secret.
`debug_mode` - Controls whether the Flask server runs in debug_mode (see the [documentation](http://werkzeug.pocoo.org/docs/0.14/debug/) for details). You should definitely set this to False in production environments

