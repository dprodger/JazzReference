things to do:
App
* hook up bad-link logging on images
* fix the default (I type in a song name; get to that song; then go back -- the text box has my song name, but the page has no search restriction)

Backend Server

Data
* Look into performer_discography vs. recording_performers
* for verify_performer_references -- provide a mode that explicitly removes references if they no longer pass the confidence threshhold
	* look for a way to log whether a reference has been "hand-entered"
* give me a list of artist names and wikipedia URLs that aren't an exact match, to identify cases to exclude
* refactor the wikipedia image stuff so that fetch_artist_images and the standalone image inserter use common code
* update the master research code to use the various components rather than recreate them
* Incorporate the metadata around the caption for images like this:
	https://en.wikipedia.org/wiki/Miles_Davis#/media/File:Howard_McGhee,_Brick_Fleagle_and_Miles_Davis,_ca_September_1947_(Gottlieb).jpg
* Lena Horne image is in the public domain, but is stored as 'all rights reserved' in the db. Figure tha tout
* Look at Dave Catney wikipedia	
* figure out consistency of external_references (_references or _links)
* running Jazz_song_research in dry-run mode, doesn't show me the musicbrainz search
* running jazz_song_research, not sure I'm getting wikipedia on finding a new song
* when running fetch_artist_images.py, it looks like it's slow either sleeping, or with db connection
* if solo_transcriptions appears, show and allow access to it
    
    
     

	
Done:
* amend fetch_artist_images to gather for all artists?
* Ensure multiple images perform ok
* given a Wikipedia image page (like this), correctly import it https://en.wikipedia.org/wiki/Miles_Davis#/media/File:Charlie_Parker,_Tommy_Potter,_Miles_Davis,_Duke_Jordan,_Max_Roach_(Gottlieb_06851).jpg
* amend verify_performer_references to only either look just for artists who don't already have refs, just those who do, or both
* remove "Images" heading from Artist view
* Add watermark on the images
* at Ron Carter and wikipedia logic. We have the wrong URL for Wikipedia for him	
* fix import_mb_releases to use --name or --id params, not just taking the name
* add a single-song path for gather_mb_ids.py
* check for propagation of DNS settings: Go here, for instance: http://linernotesjazz.com/docs
* MusicBrainz release import doesn't seem to be getting all performers
* Deal with this:
	Processing: Thelonious Monk
	2025-10-23 15:08:38,910 - INFO - ============================================================
	2025-10-23 15:08:38,910 - INFO -   Checking existing Wikipedia: https://en.wikipedia.org/wiki/Thelonious_Monk
	2025-10-23 15:08:38,911 - DEBUG - Verifying Wikipedia URL: https://en.wikipedia.org/wiki/Thelonious_Monk
	2025-10-23 15:08:38,946 - DEBUG - https://en.wikipedia.org:443 "GET /wiki/Thelonious_Monk HTTP/1.1" 200 60478
	2025-10-23 15:08:40,068 - DEBUG - Checking for 'disambiguation' in first 500 chars...
	2025-10-23 15:08:40,068 - DEBUG - Found 'disambiguation' - rejecting page
	2025-10-23 15:08:40,068 - WARNING -   ✗ Wikipedia reference may be invalid (confidence: high, score: 0)
	2025-10-23 15:08:40,068 - WARNING -     Page is a disambiguation page
	2025-10-23 15:08:40,068 - WARNING -     NOT removing reference - manual review recommended
	2025-10-23 15:08:41,573 - INFO - 
* amend fetch_artist_images to use the wikipedia reference if it exists (rather than search)
* Spotify -- examples: 
    Paul Desmond, Pure Desmond, Everything I Love
    Bill Evans, The Complete Riverside Recordings, Everything I Love (Ev'rything I Love)
    Peter Erskine, You Never Know, Everything I Love
    Chris Connor, All About Ronnie, Everything I Love
* run jazz_song_research.py with 'There's No You' -- got nothing in terms of references. Why? Also -- stripping out apostrophe?
* Whenever I pass in a song name, I need to be careful about apostrophes vs. encoded apostrophes: They Didn’t Believe Me vs There's No You
* decide on whether musicbrainz, wikipedia etc. are in a combined field (external references) or discrete fields
* normalize instruments with a category or family or something (so Guitar, Electric Guitar and Acoustic Guitar all are filterable by Guitar)
* provide filters on the song detail view to filter to just those with certain instruments (or performers?)
* when gathering_mb_releases, store the MB id in the table
* create a "bad reference" table and system -- allow me to indicate while using the App that something (musicbrainz, Wikipedia, image) is not right. 
	Use that as an exclusion, but also as possible training data for the future.
* implement the 'bad link' code






Overall approach:

for each entity, provide a script to "research them"
-- if the entity has any or all of the canonical identifiers, there should be an option to 
	verify whether with current search logic, we would get the same canonical identifiers
-- if the entity does not have canonical identifiers, we should capture and store them

--if the entity has valid identifiers, there should be an option to:
	-- verify against best search logic
	-- only add new
	-- remove all and populate with best-available
	
Maybe start this with artist
	