# The TinyFish post

Issue #34. The TinyFish track only counts if the demo is posted on X or
LinkedIn with TinyFish tagged. Draft it by Sat 6 pm, post it before you
submit, and put the link in the Devpost page.

**Do not post until there is a real run to show.** The post says the agent
read live sites. `scout/EVIDENCE.md` must list at least one completed run first.

## The clip (30 to 45 seconds)

1. **The agent working, 15 seconds.** With the backend running, run
   `python3 scout/scout.py --source parks --api http://<server>`. The terminal
   prints a "watch it live" link. Open it and screen-record the agent's
   browser reading the City of London parks page.
2. **The quest arriving, 5 seconds.** The web page: tap **Short**. The quest
   sign changes, with "Found by the scout on london.ca" under it.
3. **Gary using it, 15 seconds.** Point Gary at the thing the quest asks for,
   press the button, and show the quest completing on the page. Best: film it
   at the place the quest names. If there is no time for that, film the thing
   wherever you find one, and do not caption it as being at the park.

No voice-over needed. Three captions: "A web agent reads the city's parks
page", "It files a quest", "Gary confirms the thing, on the device".

## For X

Check the tag before you post: find TinyFish's official account from their
website, or ask at their table. Put it where `[TinyFish's account]` is.

> Our first AI employee is a scout. 🐐
>
> Every morning a [TinyFish's account] agent reads London's live park, trail and event pages and files quests for G.A.R.Y the Goat (Go Anywhere, Rediscover Yourself), a QNX handheld that names what its camera sees.
>
> Built at Hack Western 13.
>
> [clip]

That is about 250 characters once the account name is in. Trim "Built at Hack
Western 13." if the name is long.

## For LinkedIn

> We hired our first AI employee this weekend. Its job title is Scout.
>
> At Hack Western 13 our team built G.A.R.Y the Goat: a pocket mountain goat that
> grows when you go outside, find things and bring a friend. Gary needs fresh
> quests every day, in real places.
>
> So each morning a web agent built on [TinyFish's account] opens five live
> pages about London, Ontario (city parks, trails, the events calendar), reads
> them the way a person would, and comes back with real places. Our code turns
> each one into a quest, leaves out anywhere closed or risky, and files it in
> the game. Then Gary's on-device model, running on QNX on a Raspberry Pi,
> confirms the quest when you find the thing.
>
> The clip shows one run, start to finish: the agent on the city's parks page,
> the quest arriving, and Gary confirming it.
>
> Team: [names]. Repo: [link].

## Before you post

- [ ] `scout/EVIDENCE.md` lists a completed live run
- [ ] The clip shows the agent's browser on a real page, not a mock
- [ ] Every page the post counts was really read: say "five" only if five
      pages have a completed run in `scout/EVIDENCE.md`
- [ ] Gary in the clip runs the QNX build. If he does not, take "QNX" out of
      the post
- [ ] TinyFish's official account is tagged (checked, not guessed)
- [ ] Posted before submission
- [ ] The post's link is in the Devpost page, in the TinyFish paragraph
