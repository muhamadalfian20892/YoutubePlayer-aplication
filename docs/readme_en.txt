T U N E V I A
=============

Version: 1.7.4
Author: Muhammad Alfian (Technokers Lab)


HELLO AND WELCOME
-----------------
Hey there. I'm Muhammad Alfian, the guy who spends way too much time coding this project. Thank you for downloading Tunevia. I want to take some time to properly explain what this program is, why I built it, and how everything inside it actually works. 

I am totally blind, and I rely on a screen reader called NVDA to use my computer every single day. I started making Tunevia because I was getting really annoyed with using regular web browsers to listen to YouTube. Browsers eat up so much RAM, the tabs get lost when you have fifty things open, and honestly, the web interfaces are a total nightmare for screen reader users when you just want to listen to music in the background while you work.

So, I decided to build a dedicated desktop program myself. The goal was simple: make something that connects directly to YouTube and YouTube Music, loads lightning fast, plays audio without loading heavy video files unless you want to, and is 100 percent accessible using just a keyboard. 

This readme file is going to be long because I want to explain every single part of the program to you. No quick summaries here. I want you to know exactly what every button does and how the system works behind the scenes.


BEFORE YOU START: THE SETUP
---------------------------
Before we get into the fun stuff, you need to make sure the program can actually run. Tunevia is built on Python, but it relies on a couple of external things to do the heavy lifting.

First, Tunevia uses the VLC Media Player engine to actually play the sound. VLC is rock solid and handles almost any audio format you throw at it. The great news is, you do not need to install VLC on your computer! I have already included the necessary VLC files right inside the 'libs' folder of this program. It is completely portable and ready to work right out of the box.

Second, if you are running this from the raw source code rather than a compiled executable, you need to install the Python libraries. Open your command prompt or terminal inside the Tunevia folder and run the command: pip install -r requirements.txt. This installs things like wxPython for the interface and python-vlc.

Finally, there is a tool called yt-dlp. This is the magic engine that Tunevia uses to talk to YouTube, search for videos, and download files. YouTube constantly changes their website code, which breaks tools like this all the time. Because of that, you don't need to worry about installing yt-dlp yourself. Every time you open Tunevia, it quickly checks the internet in the background to see if there is a newer version of yt-dlp, and it automatically downloads it for you. If you see a little delay when you first open the app, that is what it's doing.


THE MAIN INTERFACE
------------------
When you open Tunevia, you will see a classic Windows interface. I didn't want anything too flashy or confusing. At the very top, you have a row of tabs. You can click on these with your mouse, or if you prefer the keyboard, you can hold down the Control key and press numbers 1 through 9 to jump instantly between them. 

Let's go through every single tab and what you can do inside them.


TAB 1: YOUTUBE SEARCH (Ctrl + 1)
--------------------------------
This is your starting point. At the top of this tab is a large text box. This is your search bar. You can type the name of a song, a podcast, or an artist here. But you can also just paste a direct YouTube link if your friend sent you one. You can even paste the link to an entire YouTube Playlist, and the app will understand it.

When you press Enter, the program reaches out to YouTube and pulls a list of results. The area below the search bar will fill up with these results. I designed the list so it is easy to read. Each line will show you the full title of the video, exactly how long it is, and the name of the channel that uploaded it. 

If you right-click on any item in this list, a menu opens up with a bunch of options:
- Play Audio: This instantly loads the audio of that video into the player and starts it.
- Add to Queue: If you are already listening to something, this puts the song next in line to play.
- Download: This sends the video over to the Downloader tool, which I will explain later.
- Add to Favorites: This saves the song to your Favorites tab so you never lose it.
- View videos by this uploader: This is a really cool shortcut. If you find a channel you like, click this, and Tunevia will automatically run a new search to show you only videos from that specific channel.
- Start Radio: If you click this, Tunevia will play the song, and then it will automatically find similar songs and keep playing them forever. It's like your own personal radio station.
- Copy Link: Just copies the YouTube URL to your clipboard.

Also, I built a caching system into the search. If you search for "Linkin Park", go do something else, and then search for "Linkin Park" again in the same session, it will load instantly because it remembers the results.


TAB 2: DISCOVERY (Ctrl + 2)
---------------------------
Sometimes you just want to know what is popular right now without having to search for it. In this tab, you will find two big buttons at the top. One says "Top 100 Global" and the other says "New Releases". 

When you click one of these, Tunevia goes to YouTube's official music charts and pulls the current data. The big list below the buttons will populate with all the trending songs. It works exactly like the search results list. You can double-click a song to play it, or right-click to add it to your queue or favorites.


TAB 3: RADAR (Ctrl + 3)
-----------------------
This is a feature I am really proud of. It is designed to help you find new music based purely on what you actually like, without using annoying tracking algorithms.

In this tab, there is a big button that says "Scan". When you click it, the program looks at the history of songs you have listened to recently within Tunevia. It takes a few of those songs, asks YouTube what videos are related to them, and then compiles a big list. The smartest part is that it automatically filters out the songs you have already listened to. 

So, you end up with a fresh list of recommendations tailored to your recent mood. It takes a few seconds to run the scan because it has to cross-reference a lot of data, but it is totally worth it.


TAB 4: AUDIO PLAYER (Ctrl + 4)
------------------------------
This is the command center for your listening experience. 
At the very top of this tab, there is a status text area. It tells you the exact title of what is playing, the channel name, and the view count. 

Below that, you have two horizontal sliders. The long one is the Seek Bar. You can click anywhere on it to jump to the middle of the song. The shorter one is your Volume control. If you are using a keyboard, you can use the left and right arrow keys to skip forward and backward in the song, and the up and down arrow keys to change the volume. If you ever want to know how much time is left in the song, just press the letter 'T' on your keyboard, and the program will speak the current time out loud.

Under the sliders are your main buttons: Play/Pause, Stop, Previous Track, and Next Track. 

But below those buttons is a grid of advanced tools:
- Playback Speed: A slider that lets you slow the audio down to 0.25x speed or speed it up to double speed. Great for listening to long podcasts.
- Equalizer: If you press Ctrl+E or click this button, a new window opens with a 10-band audio equalizer. You can adjust the bass and treble exactly how you like it. You can save your own presets too. There is a Pre-amp slider in there that lets you boost the volume up to 200 percent, but be really careful with it because it will distort your audio if you push it too hard.
- Audio Track: Sometimes YouTube videos have multiple language tracks. If they do, this button becomes clickable so you can choose which language you want to hear.
- Toggle Shuffle and Repeat: Buttons to mix up your playlist or loop a single song forever.
- Mono Audio: A button to force the audio into a single channel. This is really useful if you are only wearing one earphone or if a video has terrible stereo mixing.
- Spatial Audio: Press Ctrl+Shift+S to toggle Spatial Audio on or off, or press Ctrl+Shift+E to open Spatial Audio settings. You can widen the stereo soundstage and add room depth with five presets (Off, Subtle Wide, Concert Hall, Studio Room, Wide Stage) or adjust Soundstage Width, Room Size, and 3D Depth sliders while keeping memory usage low.
- Bookmarks: If you press Ctrl+B while listening, a window pops up letting you type a note. It saves that exact timestamp. Later, you can open your bookmarks and jump right back to that funny moment in a podcast or your favorite guitar solo.

There is also a button called "Show Video". By default, Tunevia only plays audio to save your internet bandwidth and computer memory. But if you actually want to watch the music video, click this, and a small, simple window will pop up showing the video feed.


TAB 5: HISTORY (Ctrl + 5)
-------------------------
Every single thing you play in Tunevia gets recorded here so you never lose track of a good song. 
Because this list can get huge, I put a search bar right at the top of the History tab. You can just type a word, and the list instantly filters down to match what you typed. You can right-click items here to play them again. There is also a button to export your entire history as a playlist file (like an .m3u file) so you can back it up.


TAB 6: FAVORITES (Ctrl + 6)
---------------------------
This is your personal collection. Whenever you right-click a song in the Search, Discovery, or Radar tabs and choose "Add to Favorites", it goes here. It functions exactly like the other lists.


TAB 7: LYRICS (Ctrl + 7) - PLEASE READ THIS PART
------------------------------------------------
Okay, I need to talk about the Lyrics tab in detail, because I have to be completely honest about a bad flaw in how the automation works right now.

The tab itself is mostly a giant text box where you can read lyrics. At the bottom, there are input boxes where you can manually type a song title and artist, click Search, and the app will grab the lyrics from Genius.com. You can also save the lyrics to a text file on your computer.

Now, in the Settings tab, there is an option called "Auto-fetch lyrics". The idea is that when a song starts playing, you don't have to do anything. Tunevia will automatically find the lyrics and put them in the box. 

But here is the bad thing: the automation is completely blind and honestly pretty dumb. Tunevia does not actually know if the YouTube video you are playing is a music video or just people talking. When a video starts, the app just grabs the title of the video, tries to delete common words like "(Official Music Video)", and throws whatever is left over to the Genius API to search for it.

If you are listening to "Coldplay - Numb", it works perfectly. But let's say you decide to listen to a 45-minute video essay about the history of Rome, or a tutorial on how to fix a leaking sink. Tunevia does not care. It will take the title "How to fix a leaking sink", send it to Genius, and blindly search for it. Because Genius has a massive database, it might actually find some obscure indie rap song that happens to have the word "sink" in the title. Suddenly, you are trying to listen to a plumbing tutorial, and the lyrics tab fills up with completely unrelated, random song lyrics. 

And it just keeps fetching. Every single time a new video plays, it searches. It doesn't care if it's a song, a vlog, or a news report. If you use Tunevia to listen to a mix of music and talking videos, this is going to get annoying really fast. It wastes internet requests and shows you nonsense. 

My honest advice? If you mostly listen to podcasts or random YouTube videos, turn the Auto-fetch setting OFF. Just leave it off. When you actually play a real song and want to sing along, just go to the Lyrics tab and use the manual search boxes at the bottom. It is much less frustrating that way. I might try to make it smarter in the future to detect if something is actually music, but for now, that is how it is.


TAB 8: STATS
------------
This is a fun little panel. It keeps track of your listening habits over time. It will show you a list of your top artists and your most played tracks. It also tries to calculate how much time you spend listening to actual music versus other types of video content. It just gives you a visual breakdown of your Tunevia life.


TAB 9: SETTINGS (Ctrl + 8)
--------------------------
This is the engine room. I tried to group everything logically so it is easy to find.

- General Group: Here you can change the language of the entire application. It updates instantly when you change it. You can also check boxes to make the Tunevia window stay "Always on Top" of your other programs, or make it minimize to the system tray (down by your clock) instead of taking up space on your taskbar. You can also turn on Clipboard Monitoring here. If this is on, anytime you copy a YouTube link anywhere on your computer, Tunevia will pop up a box asking if you want to play it or download it.
- Playback Group: You can set your default audio quality. You can change your default seek interval (when you press the arrow keys, do you want it to jump 5 seconds, 10 seconds, or a whole minute?). You can also turn on Audio Normalization here, which tries to stop quiet songs from being too quiet and loud songs from blowing your ears out.
- Search & Downloader Group: You can set the folder where your downloaded files will be saved. There is also a setting here called "Comment Fetch Limit". You can set this to 10, 20, 50, or even "All". This controls how many comments the app will load when you open the Video Comments window. (By the way, there was a bug recently that crashed the app when you tried to change this setting, but I finally fixed it in this version, so you can change it safely now).
- Sound Group: Tunevia makes little clicking and popping noises when you press buttons or finish a download. If you hate that, you can turn all the UI sounds off right here.
- Tab Management: If you never use the Radar tab or the Stats tab, you can actually uncheck them here to hide them completely. You can also change the order they appear in at the top of the screen.


TAB 10: HELP (Ctrl + 9)
-----------------------
This is just a built-in text viewer that lists all the keyboard shortcuts and gives you a quick reminder of how the features work.


THE DOWNLOADER WINDOW (Ctrl + D)
--------------------------------
Tunevia isn't just a player; it has a very powerful downloading engine built right in. You don't have to use a tab for this. Just press Ctrl+D from anywhere in the app, and a separate Downloader window will open.

The best part about the downloader is that it handles queues and batches. There is a giant text box at the top. You don't have to paste links one by one. You can copy a list of twenty YouTube links from a text file, paste them all into the box at once, and hit Add. 

When you add a link, a window pops up asking what quality you want. You can choose different video resolutions, or you can choose "Audio Only". If you choose Audio Only, Tunevia will download the raw audio and then automatically use a tool called FFmpeg to convert it into a clean MP3 file for you. 

The downloads line up in a queue list. You can see the progress percentage and the status (like "Downloading..." or "Converting..."). You have buttons to pause the whole queue, resume it, or cancel items. Also, if you close Tunevia while you still have things in the queue, it remembers them. The next time you open the downloader, your queue will still be there waiting for you.


COMMAND PALETTE (Ctrl + K)
--------------------------
If you like to work fast and hate taking your hands off the keyboard to use the mouse, you are going to love this. Press Ctrl+K anywhere in the program. A small search box will appear in the middle of the screen.

This is a search bar for actions. Instead of digging through the settings to find the dark mode switch, you just press Ctrl+K, type the word "dark", and hit enter. The app switches to dark mode. You can type "shuffle" to toggle the shuffle mode, "down" to open the downloader, or "clear" to clear your search cache. It is incredibly fast once you get used to it.


GLOBAL HOTKEYS
--------------
Sometimes you are typing a document or playing a video game, and a song comes on that is way too loud, or you just want to skip it. You shouldn't have to alt-tab out of your game just to change the song.

Because of this, Tunevia registers Global Hotkeys with Windows. This means you can control the music from anywhere on your computer, as long as Tunevia is running in the background.
- Alt + Shift + P: Plays or Pauses the music.
- Alt + Shift + N: Skips to the Next track.
- Alt + Shift + B: Goes back to the Previous track.
- Alt + Shift + Up Arrow: Turns the volume up.
- Alt + Shift + Down Arrow: Turns the volume down.
- Alt + Shift + Left/Right Arrow: Rewinds or fast-forwards the current song.


VIDEO COMMENTS VIEWER
---------------------
Sometimes the best part of a YouTube video is reading the comments while you listen to the audio. I added a feature for this. While a song is playing in the Audio Player tab, you can pull up a specific window to view the comments. It strips away all the heavy website graphics and just gives you a clean text list of what people are saying, based on the limit you set in your settings.


A NOTE ON BUGS AND WEIRD BEHAVIOR
---------------------------------
I build this in my spare time, so it's not perfect. There are a few things you should know.

Sometimes you will try to play a video and it will just skip or say it failed. 90 percent of the time, this is because the video is Age-Restricted by YouTube. YouTube requires you to be logged into an account to prove your age for those videos. Since Tunevia doesn't have a login screen, YouTube blocks the app from reading the file. There is a way around this using a "cookies.txt" file from your browser, which you can load in the Settings tab, but it can be a bit technical to set up.

Also, remember what I said about the Lyrics tab. If it's giving you crazy results, just turn off the auto-fetch. 


CONTACT AND OPEN SOURCE
-----------------------
Tunevia is completely open source. I don't make money off this; I just wanted to build a tool that makes listening to music easier for everyone, especially for folks like me who use screen readers to navigate their PCs. If you know how to code in Python and want to look at how I built the VLC integration or the NVDA speech engine hooks, the code is all yours to look at. You can modify it, fix my mistakes, or add your own features.

If you run into a bug that breaks the program, or if you just have a really cool idea for a feature that I haven't thought of, please reach out to me. I'm always trying to make this thing better.

You can email me at: hafiyanajah@gmail.com
Or you can find me on GitHub at: muhamadalfian20892

Thank you so much for giving Tunevia a try. I hope you enjoy listening to your music with it as much as I enjoyed building it. 

- Muhammad Alfian (Technokers Lab)