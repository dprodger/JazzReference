things to do:
App
* hook up bad-link logging on images
* fix the default (I type in a song name; get to that song; then go back -- the text box has my song name, but the page has no search restriction)

Backend Server
* amend fetch_artist_images to use the wikipedia reference if it exists (rather than search)

Data
* MusicBrainz release import doesn't seem to be getting all performers
* for verify_performer_references -- provide a mode that explicitly removes references if they no longer pass the confidence threshhold
	* look for a way to log whether a reference has been "hand-entered"
* give me a list of artist names and wikipedia URLs that aren't an exact match, to identify cases to exclude
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
* create a "bad reference" table and system -- allow me to indicate while using the App that something (musicbrainz, Wikipedia, image) is not right. 
	Use that as an exclusion, but also as possible training data for the future.
* refactor the wikipedia image stuff so that fetch_artist_images and the standalone image inserter use common code
* update the master research code to use the various components rather than recreate them
* Incorporate the metadata around the caption for images like this:
	https://en.wikipedia.org/wiki/Miles_Davis#/media/File:Howard_McGhee,_Brick_Fleagle_and_Miles_Davis,_ca_September_1947_(Gottlieb).jpg
* Lena Horne image is in the public domain, but is stored as 'all rights reserved' in the db. Figure tha tout
* Look at Dave Catney wikipedia	
* decide on whether musicbrainz, wikipedia etc. are in a combined field (external references) or discrete fields
* figure out consistency of external_references (_references or _links)
* implement the 'bad link' code
* run jazz_song_research.py with 'There's No You' -- got nothing in terms of references. Why? Also -- stripping out apostrophe?
* Whenever I pass in a song name, I need to be careful about apostrophes vs. encoded apostrophes: They Didn’t Believe Me vs There's No You
* running Jazz_song_research in dry-run mode, doesn't show me the musicbrainz search
* running jazz_song_research, not sure I'm getting wikipedia on finding a new song
* when gathering_mb_releases, store the MB id in the table



Argument standardization:

	
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
