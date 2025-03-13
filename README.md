# Navigation:

For easy navigation, this file has been split into sections. You can jump easily to each section by searching for two plus signs with a space between them: `+ +`.

# YouTube Player

**The Accessible YouTube Browser and Downloader.**

**By Technokers Lab**

## + + Quick Start

You've just downloaded this piece of software, and you don't want to spend an hour reading this extensively well-written manual. You just want to dive in!

So, here's a list of things you need to know to use YouTube Player. Anything more, you'll either figure out on your own or can come back here to read about later:

*   To search for videos, type your query in the search box and press Enter.
*   Right-click on a search result to access options like "Open in Browser," "View Description," "Download," and "Play".
*   To play the audio of a video, right click on the video and select "Play".
*   The audio player has Rewind, Fast Forward, Play/Pause and Close buttons. You can also see the elapsed and total time.
*   To download videos, click the "Run Youtube DL" button, or right-click a search result and choose "Download with Youtube DL".
*   Downloaded videos will be saved in the directory you choose.  You can set the default download directory in the "Youtube DL" section.
*   You can exit the program using the exit button.

**Contents:**

*   Introduction
*   The Search Screen
*   The Youtube DL Screen
*   The Audio Player Screen

## + + Introduction

### What is YouTube Player?

YouTube Player is a desktop application designed to make searching, playing, and downloading YouTube videos easier and more accessible. It combines a powerful search interface with the capabilities of `yt-dlp` (a popular video downloader) in a user-friendly way.

### This documentation.

This documentation is laid out with each major feature having its own section. This is in hopes that if you wish to read about, or be reminded about, a specific feature, you can easily find that section and browse.

### Upon first opening the player.

When you first open the player, you'll be presented with the Search screen.  From there, you can start searching for videos immediately.

## + + The Search Screen

### What is this screen for?

This is the main screen of the application.  From here, you can:

*   Search for YouTube videos.
*   View search results.
*   Access context menus for each video (right-click).
*   Load more search results.
*   Run the YouTube DL downloader.

### The screen's layout.

The screen is laid out with the following elements:

*   **Search Box:**  Type your search query here and press Enter.
*   **Results List:**  Displays the search results.  Each result shows the video title and uploader.
*   **Load More Button:**  Click this to load more search results (if available).  It will disappear once all results are loaded, or if the maximum search results have been reached.
*   **Run Youtube DL Button:** Opens the YouTube DL downloader for manually entering links.
*   **Exit button:** Closes the program.

### Context Menu.

Right-clicking on a video in the Results List brings up a context menu with these options:

*   **Open in Browser:** Opens the video in your default web browser.
*   **View Channel:** Opens the video's channel in your browser.
*   **View Description:** Shows the video's description in a separate window.
*   **View Video Details:** Shows detailed information about the video (title, uploader, duration, views, upload date, likes).
*   **Download with Youtube DL:** Opens the YouTube DL downloader with the video's link pre-filled.
*   **Play:** Play the audio of the selected video.
*   **Copy:**
    *   **Copy Video Link:** Copies the video's URL to your clipboard.
    *   **Copy Channel Link:** Copies the channel's URL to your clipboard.
    *   **Copy Title:** Copies the video's title to your clipboard.

## + + The Youtube DL Screen

### What is this screen for?

This screen allows you to download videos using the power of `yt-dlp`. You can access it either by clicking the "Run Youtube DL" button on the Search screen or by right-clicking a search result and choosing "Download with Youtube DL".

### The screen's layout.

The screen contains the following elements:

*   **Links to download (one per line):** Enter one or more video links here, each on a new line.
*   **Download subtitles:** Check this box to download subtitles along with the video.
*   **Download description:** Check this box to save the video's description to a text file.
*   **Convert to MP3:** Check this box to convert the downloaded video to MP3 audio format.
*   **Download directory:**  Enter the path where you want to save the downloaded files.
*   **Browse Button:** Click this to choose the download directory using a file dialog.
*   **Download Button:** Click this to start the download process.
*   **Progress List:** Shows the progress of each download.
*   **Close Button:** Closes the YouTube DL screen.

### Messages:

The Progress List will display messages during the download process:

*   **Preprocessing:**  The program is gathering information about the video.
*   **Downloading [filename]: [percentage]:** Shows the download progress for a specific file.
*   **Complete: [filename]:**  Indicates that a file has finished downloading.
*   **Error: [link or filename]:**  Indicates an error occurred during the download.  The file may be incomplete or corrupted.

### Important Note:

While YouTube Player provides the capability to download videos, please be mindful of copyright and YouTube's Terms of Service. Only download videos that you have permission to download (e.g., public domain content, videos with a Creative Commons license, or videos where the creator has explicitly granted permission).  The user is responsible for ensuring they comply with all applicable laws and terms of service.

## + + The Audio Player Screen

### What is this screen for?

This screen allows you to listen to the audio of a YouTube video without needing to keep a browser window open.

### Screen Layout

The screen is laid out as follows:

*   **Time Text:** Shows the elapsed time and total duration of the audio.
*   **Rewind Button:** Rewinds the audio by 10 seconds.
*   **Fast Forward Button:** Fast forwards the audio by 10 seconds.
*   **Play/Pause Button:** Plays or pauses the audio.
*   **Close Button:** Closes the audio player.
*   **Error Text:** Displays error messages.

### How to use it:

Right-click on a video in the Search Screen and select "Play". The audio player will open and begin fetching the audio. Once the audio is loaded, a notification sound will play, and playback will start automatically (if auto-play is enabled). You can control playback using the buttons provided.

### Important Notes:

*   If there is an error loading the audio, an error message will be displayed in the "Error Text" area, and the play/pause button will be disabled.

---

_last modifyed: 07 March 2025 20:30 GMT at version 1.2.0_
