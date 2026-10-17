# PB Vision: partner request

Notes for applying to PB Vision's partner API (their Zendesk "Contact us" form), written
17 Oct 2026. The plan this serves is "Video" in `../growth-plan.md`. Update this page with
their answers.

## The form

**Your name:** Teja

**Email address:** `hello@popshotpb.com`. It forwards to the owner's inbox through Cloudflare
Email Routing.

**How can we help you?**

```
Tell us about your app so we can get you set up:

- Who it is for:
Popshot (popshotpb.com) is a pickleball app for crews: groups of friends who play together
every week. We're in an open trial now, starting in the US, with players elsewhere already.
The person we build for is the crew lead or organiser, who keeps the group playing; the
players are their friends.

- What it does:
Crews log games in seconds, plan meetups with RSVPs and reminders, and get a recap after
each day of play: the scores, friendly awards (Close Call, Great Partner, Welcome Wagon) and
a short story of the day they can share in WhatsApp. Players also get a personal "journey":
what they're working on, and check-ins every two weeks with tips and videos picked for them.
We're friendly by design: no public rankings, private by default, and nothing that shames
anyone. Players who want a rating use DUPR alongside us.

How we want to stand out: we're the crew's memory. Other apps give you a rating or a court
booking; Popshot remembers every game, partnership and rivalry, and tells the story after you
play. Adding your analysis lets us show each crew how the game was actually played and what
each player could work on next, in that same encouraging voice.

- The PB Vision data you need:
A pilot of about 30 games a month across a few crews, recorded on players' phones and
uploaded through our app (server to server; your key never reaches a browser). For each game
we'd like:
1. Highlight clips (or rally timestamps we can clip from).
2. Per-player stats: shot mix, third-shot drops vs drives, time at the kitchen line,
   unforced errors, rally length.
3. The rally-by-rally score timeline.
4. Player identification without face recognition, for example the uploader choosing who is
   who.
5. A webhook when processing finishes.

We'd show results in our own design, credited "Analysed by PB Vision", only to the crew
members who played, and we'd delete the raw video soon after processing.

Questions:
- Your partner rate per hour of HD video, and whether the Annual Premium pass is required.
- Whether highlights are available through the API.
- Whether we may keep the stats after the video is deleted, and where videos are processed
  and stored.
- Typical processing time.

Thanks!
```

**Attachments (optional):** phone screenshots of a recap and a crew page.

## Before sending

- Check "starting in the US, with players elsewhere already" is still true.
- "Unforced errors" and "rally length" are guesses at what they measure; their answer
  confirms what's available.
- The raw-video deletion period is left open on purpose (the plan says 14 days) until their
  storage terms are known.

## What we know so far (public pages, Oct 2026)

- Partner rate about $8 per hour of HD video (about $1.60 for a 12-minute game); 4K about $12
  an hour; negotiated per partner.
- API access needs the Annual Premium pass ($396 a year) and their approval.
- Processing takes 3 to 24 hours.

## Their answers

Not sent yet.
