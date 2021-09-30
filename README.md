# mr.white
A discord bot.
Designed for my own use.

# Setup
`python mr.white.py <TOKEN>`

# Commands
```
Streamer:
  add      Add a song to the playlist through keywords or youtube url
  clear    Remove all the musics.
  current  Show the current music.
  del      Delete a song (remove from playlist and delete from random list)
  loop     Set the switch of loop on the playlist.
  next     Play next music.
  pick     Pick a music to the top of playlist.
  playlist Show the playlist.
  reload   Reload random playlist.
  remove   Remove a music from the playlist.
  repeat   repeat the current music for up to 10 times.
  restart  Restart the player. Plaeas use it when the player is freezing.
  start    Start the player.
  stop     Stop the player.
No Category:
  help     Shows this message
  meme     Explain the source and meaning of input meme.
  mp3      Search for and download mp3 according key words.
  py       Label pinyin to inputs Chinese.
  tr       Translate between Chinese and English.
  wiki     Search for input query from wikipedia.zh

Type -help command for more info on a command.
You can also type -help category for more info on a category.
```

# Dependencies
* discord.py[voice]
* pysocks
* pafy
* youtube-dl
* pypinyin
* [Transfer](https://github.com/Mikubill/transfer)

# TODO:
- [ ] pause/play
- [ ] Pages of playlist
- [ ] Update the player UI
