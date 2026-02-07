# 🎵 Moojik: The "Democratic" Aux Cord Manager

**Status:** *Stable (unlike your friends' music taste)*

## What is this?

You are hosting a gathering. You want music. 
Your friends want to play music. 
**The problem:** Your friends have terrible taste, and passing the phone around results in a chaotic mix of sad indie folk followed immediately by Death Grips.

**The Solution:** **Moojik**. 

This is a local web app that gives your guests the *illusion* of choice while you, the Host, retain absolute, dictatorial power from the safety of your command line.

## The Power Dynamic

### 1. The Peasants (Your Guests)
They get a shiny web interface (`http://<YOUR_IP>:5000`).
- They can paste YouTube links.
- They can type their name (so you know exactly who to blame).
- They see an "Estimated Wait Time" (which is a lie if you decide to delete their song).
- They see a "Rejected History" list, serving as a public wall of shame.

### 2. The Overlord (You)
You get a hackers-only Terminal User Interface (TUI).
- **See the future:** View the queue before it plays.
- **Judge silently:** See the song title and the culprit's IP address.
- **Wield the Hammer:** 
    - Press `SPACE` to graciously allow the song to grace your speakers.
    - Press `D` to banish the song (and the submitter's hopes) to the Shadow Realm (Rejected List).

## "Features"

- **Risk-Free DJing:** Verify the video title before opening it. No more accidental "10 hours of Nyan Cat".
- **Public Shaming:** The web UI displays rejected songs, so everyone knows that Kevin tried to queue "Cotton Eye Joe" for the third time.
- **Wait Time Calculator:** sophisticated math (current index * 4 minutes) to keep them patient.
- **Zero Database:** Everything is stored in RAM. If the vibe gets too weird, just restart the app and gaslight everyone into thinking it never happened.

## How to Install

You need Python. If you don't know what that is, you probably shouldn't be entrusted with the aux cord anyway.

1.  **Clone this repo** (or just copy the files, I'm not a cop).
2.  **Install dependencies:**
    ```bash
    pip install flask textual beautifulsoup4 requests
    ```
3.  **Run the beast:**
    ```bash
    python app.py
    ```

## How to Rule (Controls)

Once the app is running, you will see a cool table in your terminal.

- `SPACE`: **Play**. Opens the video in your default browser. The crowd goes wild.
- `D`: **Delete/Reject**. Sends the song to the rejection pile. Use this when you see "Bagpipes 10 hour version".
- `Q`: **Quit**. Shut it down. Go to bed.

## FAQ

**Q: Can I use Spotify links?**
A: No. This parses YouTube HTML metadata with regex and prayers. Take it or leave it.

**Q: Is this secure?**
A: It's a Flask dev server running in a thread next to a TUI loop. It's about as secure as a screen door on a submarine. Do not run this on public Wi-Fi unless you want strangers adding weird stuff to your queue.

**Q: Why does the UI freeze?**
A: It doesn't anymore! I fixed the threading deadlock. If it freezes now, it's probably your computer judging you.

---
*Built with hate for bad music and love for Python.*
