# guitube

配套youtube-dl使用的网页和服务端
后台部分由python3+flask实现，前端是vue。已经新增requirement.txt文件，可直接通过宝塔、gunicorn启动。
我当前测试的版本是3.6.8，正常情况下3.6或者3.7均可使用。

![alt text](https://github.com/MRDHR/guitube/blob/master/doc/example.png "Guitube in action")

以下为原fork写的文章，大部分功能已经隐藏。

Formerly known (to me at least) as PiTube, because it started as a program I wrote to run on a RaspberryPi.

Now written in Vue.js and with partial imgur support!

Video playback is now possible for WEBM and MP4 videos, and the default configuration will attempt download videos it can play back if it can do so without compromising video quality.

## Getting started

Before you can use guitube, you'll need to install Python 3, Flask and youtube-dl.

You can install python from [Python.org](https://www.python.org/)

That will also install pip, a python package management tool. You can use that to install flask and youtube-dl by running the following command:

```bash
pip install Flask
pip install youtube-dl
```

Then just run `python3 PiTube3.py` to start the server.

The webpage it serves will be accessible via your browser, on localhost:5002 (configurable in the config file)

On first run, the program will create a config.ini file. This contains all the settings for the application

## config.ini

The .ini file contains the two sections, 'Downloader' and 'Server':

### Downloader

`download_folder` - The folder that downloaded files are downloaded to. This needs to exist or downloads will fail. It should also be an absolute path.

`download_queue` - The file that the current download queue will be saved to. This is used to persist the queue between restarts of the application. This will be created if it doesn't exist, so you can delete it to delete the queue if you want, although you could just delete them on the page instead.

`dumb_download_queue` - Ignore this, it's dumb.

`download_format_string` - This controls the formats that youtube-dl will try to download. See [youtube-dl's documentation](https://github.com/rg3/youtube-dl/#format-selection) for more details on how to customise it to your preferences. The default value we use is `bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best` This will first try to download the best quality video regardless of format, and will try to download the best quality m4a audio, so that the merged file can be an MP4 file. If this is not possible, it will fallback to the best quality audio in general, which might let it be a WEBM file, but will probably need to be MKV, and if it can't do that for some reason, it will download the best quality it can. WEBM and MP4 containers can be played back by most modern browsers using the VIDEO tag, hence the preference.

### Server

Server settings are configuration passed through to the built in Flask server

`host` - When set to 0.0.0.0, the hosted pages will be visible to other users on the network. When set to 127.0.0.1 they will only be visible on the computer running the application.

`port` - The port number that the server will be accessible using.

`secret_key` - The secret key used to encrypt secure session cookies. It doesn't really matter what this is, as long as it's secret. This is automatically generated the first time you run the program.

`debug_mode` - Controls whether the Flask server runs in debug_mode (see the [documentation](http://werkzeug.pocoo.org/docs/0.14/debug/) for details). You should definitely set this to False in production environments
