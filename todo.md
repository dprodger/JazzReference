things to do:
App
* hook up bad-link logging on images

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
* consider pulling from https://thejazztome.info/about/
* recoridngDetailView seems to have backend URLs in it -- clean that up?
* Fix Sendgrid domain stuff and update remainder of emails



Done:
* API should use dedicated domain (api.approachnote.com) rather than www.approachnote.com/api -- fix that thruout
* fix the default (I type in a song name; get to that song; then go back -- the text box has my song name, but the page has no search restriction)
* amend fetch_artist_images to gather for all artists?
* Ensure multiple images perform ok
* given a Wikipedia image page (like this), correctly import it https://en.wikipedia.org/wiki/Miles_Davis#/media/File:Charlie_Parker,_Tommy_Potter,_Miles_Davis,_Duke_Jordan,_Max_Roach_(Gottlieb_06851).jpg
* amend verify_performer_references to only either look just for artists who don't already have refs, just those who do, or both
* remove "Images" heading from Artist view
* Add watermark on the images
* at Ron Carter and wikipedia logic. We have the wrong URL for Wikipedia for him	
* fix import_mb_releases to use --name or --id params, not just taking the name
* add a single-song path for gather_mb_ids.py
* check for propagation of DNS settings: Go here, for instance: http://approachnote.com/docs
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
* if solo_transcriptions appears, show and allow access to it
* chet (mono) not found on spotify matching (how high the moon)
* Dellington Indigos not matched for spotify


Data problems:
    2025-12-02 13:22:14,841 - DEBUG - [77/88] Ella Fitzgerald at the Opera House
    2025-12-02 13:22:14,841 - DEBUG -     Artist: Ella Fitzgerald
    2025-12-02 13:22:14,841 - DEBUG -     Year: 2017
    2025-12-02 13:22:14,841 - DEBUG - Cache hit: search_album_99d445fd069e014475278a69313793f6.json
    2025-12-02 13:22:15,141 - DEBUG - Simple database connection created
    2025-12-02 13:22:15,141 - DEBUG - Cache hit: album_1CnbixG8kZbknL8ryNXbKn.json
    2025-12-02 13:22:15,141 - DEBUG -     Matching tracks (18 tracks in album)...
    2025-12-02 13:22:15,441 - DEBUG - Simple database connection created
    2025-12-02 13:22:15,586 - DEBUG - Transaction committed successfully
    2025-12-02 13:22:15,587 - DEBUG - Database connection closed
    2025-12-02 13:22:15,588 - DEBUG -       No track match for 'Don’cha Go ’Way Mad'
    2025-12-02 13:22:15,588 - DEBUG -       Album tracks: ["It's All Right With Me - Live At The Chicago Opera House,1957", 'Don Cha Go Way Mad - Live At The Chicago Opera House,1957', 'Bewitched, Bothered And Bewildered - Live At The Chicago Opera House,1957', 'These Foolish Things - Live At The Chicago Opera House,1957', 'Ill Wind - Live At The Chicago Opera House,1957', 'Goody, Goody - Live At The Chicago Opera House,1957', 'Moonlight In Vermont - Live At The Chicago Opera House,1957', 'Them There Eyes - Live At The Chicago Opera House,1957']... (+10 more)
    2025-12-02 13:22:15,588 - INFO - [77/88] Ella Fitzgerald at the Opera House (Ella Fitzgerald, 2017) - ✗ Album matched but track not found (possible false positive)

2025-12-02 13:22:15,589 - DEBUG - [80/88] The Complete Decca Singles Vol. 4: 1950–1955
2025-12-02 13:22:15,589 - DEBUG -     Artist: Ella Fitzgerald
2025-12-02 13:22:15,589 - DEBUG -     Year: 2017
2025-12-02 13:22:15,590 - DEBUG - Cache hit: search_album_963731962116f002b857e59f63c3a4ea.json
2025-12-02 13:22:15,899 - DEBUG - Simple database connection created
2025-12-02 13:22:15,899 - DEBUG - Cache hit: album_3nXCCfwBpz0FlUdxJrMfwM.json
2025-12-02 13:22:15,899 - DEBUG -     Matching tracks (50 tracks in album)...
2025-12-02 13:22:16,208 - DEBUG - Simple database connection created
2025-12-02 13:22:16,357 - DEBUG - Transaction committed successfully
2025-12-02 13:22:16,357 - DEBUG - Database connection closed
2025-12-02 13:22:16,358 - DEBUG -       Parenthetical fallback: 27.27272727272727% → 39.02439024390244%
2025-12-02 13:22:16,359 - DEBUG -       Parenthetical fallback: 39.28571428571429% → 40.0%
2025-12-02 13:22:16,359 - DEBUG -       Parenthetical fallback: 26.470588235294112% → 29.268292682926834%
2025-12-02 13:22:16,361 - DEBUG -       No track match for 'Don’cha Go ’Way Mad'
2025-12-02 13:22:16,361 - DEBUG -       Album tracks: ["Baby, Won't You Say You Love Me", "Don'cha Go 'Way Mad", 'Solid As A Rock', 'Sugarfoot Rag', 'M-I-S-S-I-S-S-I-P-P-I', "I Don't Want The World (With A Fence Around It)", "I've Got The World On A String", 'Peas And Rice']... (+42 more)
2025-12-02 13:22:16,361 - INFO - [80/88] The Complete Decca Singles Vol. 4: 1950–1955 (Ella Fitzgerald, 2017) - ✗ Album matched but track not found (possible false positive)


* Get rid of Recording-level performers and spotify links
* add Apple authentication and whatever else was on the auth path.

* Pull release imagery from MusicBraizn
* use date of artist-credits to dictate the recording date?
* SongDetailView recording List showing different release metadata than RecordingDetailView

* match_spotify taking a recording_id to look for just that recording & releases

* what to do with song that has two or more musicbrainz IDs? (A Child Is Born is a good example of this)


## Apple Music Catalog Hosting Analysis (2025-12-20)

**Current situation:**
- Apple Music catalog: ~20GB albums + ~40GB songs as parquet files
- Built indexed DuckDB database: 12GB (albums-only mode)
- Currently on laptop, not accessible to Render-hosted backend
- Need access for song_research thread to match recordings

**Recommended: MotherDuck (DuckDB Cloud)**

Why it fits for this project:
- **Simplicity**: Upload existing DuckDB file, change one connection string, done
- **Cost**: Free tier includes 10GB storage and 10M query units/month
  - 12GB DB is slightly over free tier - either pay small overage or trim fields
- **Performance**: Cloud infrastructure, faster than laptop, queries run server-side
- **Batch-friendly**: No paying for idle time, just when actually querying

Migration steps:
1. Sign up at motherduck.com
2. Upload `apple_music_catalog.duckdb` file
3. Update `AppleMusicCatalog` class to connect via `md:` connection string
4. Done

**Alternative options considered:**
- S3 + DuckDB httpfs: Very cheap storage (~$0.30/month), but slower queries
- Small VM (DigitalOcean): $5-10/month, full control, another server to manage
- Render Persistent Disk: Everything in one place, but max 100GB and extra cost
- Load into PostgreSQL: Single database, but adds 12GB+ and different query patterns

---

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
	
