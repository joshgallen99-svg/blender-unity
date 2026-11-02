# Owner feedback (verbatim)

The owner's latest playtest notes, word for word. The prioritised plan is in `docs/handoff-local.md`.
The owner is adding their reference images separately: the Offroad Horizons Jeep, a jungle
rock-crawl, a trophy-raid UAZ in a bog, RC crawlers on rocks, and their favourite, SnowRunner's
Scout on lichen-covered granite above an autumn valley.

## Earlier message (with two screenshots of the desert)

> none of the ui works and it looks small - i can see overlapping textures in the background And in
> the second image, you can see that some of the textures and objects almost look like they're
> inverted, like I can see right through them. So yeah, please fix all of these issues and any more
> issues you find along the way.

(Fixes for these were pushed but are not yet verified on the Mac; see `docs/handoff-local.md`.)

## Playtest notes

> Okay, so just playing with it. The R button is like a good idea. But if you spam it, you can go up
> really high. A bunch of the objects you can really easily clip through, which isn't good whatsoever.
> Also, change the model. The model needs to be more of like just a better model of like a Jeep or
> something, or like a really good off-roading car. And then the suspension should be a lot more
> accurate. Also, when you're driving, it should be like easier to drive over like rocks and things,
> and there should be a bunch of rocks obscuring the path, and just things like that. Just really
> intentionally think about the level design and having things obscure pathways, things like that.
> Like, I don't want it to just be road. Like, there should be a lot of technical skill involved of
> climbing over these things and, you know, using your using everything. Like, you should be able to
> change gears as well. You should be able to like click a button to go auto mode or manual mode, and
> then in manual you could just do gear one, and then you can pretty much climb up anything as long as
> it's not bloody like close to vertical. Yeah, the game right now is super unplayable. It's bad in
> pretty much every way. I think the car needs to be able to go faster. You should be able to like
> kind of drift if you like time it right. There should be like particle effects coming out of the
> ground when you like drive, kind of thing. Yeah, right now all the objects look like they've just
> been thrown around. Just really, really intentionally put these everywhere, and yeah, just think a
> lot harder about how you can do it to make it just a really polished game in every possible way.
> Don't think about getting too many images, because I know that slows your workflow down a lot. Just
> try and do everything that I've said and then look at the images to iterate, and try and do this in
> like the most efficient way possible. But yeah, right now, like, it's decent, but it's also really
> shit. I'll also paste in a few photos from other games that I like the look of in terms of like
> level design, or not level design, but like just kind of off-roading features and everything. So
> yeah, there's a lot to work on, and that's not necessarily a bad thing, but it just means that it's
> a thing, you know. So yeah, but good work so far. It's coming along well. I also want like a lot of
> rock crawling involved. And yeah, just things like that where it's really technical stuff. And
> that's what kind of sets the game apart and makes it fun. So yeah, we really need to work hard on
> that and just, yeah, just try and improve it in every way. Like right now, the physics feels off.
> Like, I feel like you should be able to go, yeah, faster. The gravity isn't right. Yeah, you should
> be able to crawl over things. There should be times where, like, your car's, like, tilted so much
> and you've got to, like, worry about if it's, like, falling over, if it's doing this, if it's doing
> that. UI is messed up. I already said that. Just hopefully you fix it. But, yeah, there's a lot of
> things that need to be improved. The last image I just uploaded there, that's my absolute favorite.
> If the game could look like that, that would be a dream come true. But yeah, let me know, because I
> know it would be a hell of a lot easier and faster and more efficient if you could just pull assets
> from the internet. If you can't do that, and you think it's worth it, maybe we could create like a
> handoff prompt and restart this session natively on my app, or on my computer, sorry, using the
> command line interface. But yeah, like that last one, like that is exactly how I want this game to
> look.

## Setup notes for the next session

- Internet access is now enabled for cloud sessions: Poly Haven, ambientCG, Sketchfab and PyPI are
  reachable; Fab refuses automated access.
- Remote Control is on, and the owner's shared Mac folder is **`driving_sim`**. If it's empty, clone
  this repo into it.
- Planned split: Blender, asset downloads and code in the cloud, pushed to GitHub; on the Mac, pull,
  run Unity 6000.0.32f1, rebuild the scenes, play, screenshot and iterate.
