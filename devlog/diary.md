# Development diary

Draft written by the AI assistant from the working log of the day; the author edits it before it goes public.
The full, unedited conversation with the assistant is exported next to this file.

## Day 1 — Friday, 13 November

**The idea.** A spaceship is falling into a black hole. Space is bent so badly that a door no longer leads
to the next room: it leads wherever the contents of your pocket decide. Until you walk through, the door is
undecided. You have four pocket slots, a notebook with notes left by other versions of yourself, and one job:
find the set of things that makes a door open into the engine room.

**Morning: a game without an engine.** Unreal was still installing, so the day started with the part that
does not need it: the run generator, written as plain Python. One seed in, a whole run out — which of the
16 items matter, which are junk, what lies in which room, what every note says. Notes never lie.
Then a simulator played ten thousand runs with three kinds of players. The one who reads the notes always
wins, in five doors. The one who picks things at random practically never does. A patient brute-forcer
wins about 3% of the time. That was the target: reading has to beat guessing.

**Midday: tools for myself.** I work alone and my strength is 3D assets, so the assistant built a small
"asset studio": a folder per asset, one text file with the idea and the prompt, and a web page that shows
what stage each asset is at — prompt, picture, generated mesh, Blender file, final model. No database.

**Afternoon: first time in Unreal.** I had never opened Unreal before; my previous engine was Godot.
The editor's experimental MCP plugin lets the assistant work inside the editor, which helped a lot,
but the first hours went to the boring part: Xcode, toolchains, a server that would not show up.
By the evening the generator was ported to C++ line by line and checked against the Python original
on seven seeds — the dumps match exactly.

**Rooms that change around you.** There is no teleport. When the airlock closes behind you, the room you
left is removed and the next one is put in place so that its airlock is the one you are standing in.
Nine kinds of rooms, all grey boxes for now, built by a script rather than by hand.

**Playtesting changed the rules three times.** Running around the grey rooms, I found things the document
did not show:

- anomalies appeared at random, but they should depend on what you carry — so now the right path is safe,
  and it is the wrong combination that hurts;
- not "dangerous items" but dangerous combinations;
- with the same pocket, every new door must lead to the same room with the same things in it.
  It does not matter which door you open. It matters what is in your hands.

**Enemies.** Four anomalies (discharges, radiation, a gravity failure, slowed time), a mad maintenance
robot, rats, an echo that repeats your steps — and "another you". The assistant's first version locked
the doors of a dangerous room until you pulled an emergency lever. I threw that out: walking back out
of a bad room should be allowed. The rule now: an anomaly does not hold you; a human follows you from
room to room until you kill him; small things stay where they are unless they slip through the door with you.

**Making the rule visible.** A judge has a few minutes. So every door has a sign — dashes while the door is
undecided, the room's name once it is known — and while the airlock is closed the pocket slots light up
one by one, as if the door were reading them. One sentence appears once: "Doors lead where your pocket decides."

**Art direction, the long way round.** The first generated hero looked wrong. I asked for stylized graphics,
got something cartoonish, went back, and finally found the words: realistic proportions, but textures
painted by hand with rough, ragged brush strokes. The hero is now two models, a body and a head,
so the face gets all the detail.

**Where the day ended.** A run can be played from waking up on the bridge to "YOU ESCAPED":
an automated playthrough does it in five doors on the three seeds it was run on. Everything is still made of grey boxes.

**Tools used today.** Unreal Engine 5.8, Claude Code (design discussion, all code, editor automation),
Tripo and Nano Banana (first asset tests), Blender.

**Tomorrow.** Art: the hero, the items, the ship. Sound. A name for the game.
