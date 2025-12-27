// ExtractMusicBrainzData.js
// Combined JavaScript preprocessing file for extracting both artist and song/work data from MusicBrainz
// This runs in the Safari extension context before the share sheet appears

var ExtractMusicBrainzData = function() {};

ExtractMusicBrainzData.prototype = {
    run: function(arguments) {
        // Extract the URL to determine page type
        var url = document.location.href;

        // Determine page type and extract appropriate data
        if (url.includes('musicbrainz.org/artist/')) {
            this.extractArtistData(arguments, url);
        } else if (url.includes('musicbrainz.org/work/')) {
            this.extractSongData(arguments, url);
        } else if (url.includes('youtube.com/watch') || url.includes('youtu.be/')) {
            this.extractYouTubeData(arguments, url);
        } else {
            arguments.completionFunction({
                "error": "This extension works on MusicBrainz artist/work pages or YouTube videos",
                "url": url
            });
        }
    },
    
    extractArtistData: function(arguments, url) {
        // Extract MusicBrainz artist ID from URL
        var mbidMatch = url.match(/\/artist\/([a-f0-9\-]+)/);
        var musicbrainzId = mbidMatch ? mbidMatch[1] : "";
        
        // Extract artist name from the page title or h1
        var name = "";
        var nameElement = document.querySelector('h1 a[href*="/artist/"]');
        if (nameElement) {
            name = nameElement.textContent.trim();
        }
        
        // Extract biography/annotation
        var biography = "";
        var annotationDiv = document.querySelector('.annotation');
        if (annotationDiv) {
            var clone = annotationDiv.cloneNode(true);
            var buttons = clone.querySelectorAll('button, a.toggle');
            buttons.forEach(function(btn) { btn.remove(); });
            biography = clone.textContent.trim();
        }
        
        // Extract birth date
        var birthDate = "";
        var birthElement = document.querySelector('dd.begin-date');
        if (birthElement) {
            var dateText = birthElement.textContent.trim();
            // Extract just the date in YYYY-MM-DD format
            var dateMatch = dateText.match(/(\d{4}-\d{2}-\d{2})/);
            if (dateMatch) {
                birthDate = dateMatch[1];
            }
        }
        
        // Extract death date
        var deathDate = "";
        var deathElement = document.querySelector('dd.end-date');
        if (deathElement) {
            var dateText = deathElement.textContent.trim();
            // Extract just the date in YYYY-MM-DD format
            var dateMatch = dateText.match(/(\d{4}-\d{2}-\d{2})/);
            if (dateMatch) {
                deathDate = dateMatch[1];
            }
        }
        
        // Extract instruments
        var instruments = [];
        var instrumentElements = document.querySelectorAll('dd.instrument a');
        instrumentElements.forEach(function(element) {
            var instrumentName = element.textContent.trim();
            if (instrumentName && instruments.indexOf(instrumentName) === -1) {
                instruments.push(instrumentName);
            }
        });
        
        // Extract Wikipedia URL
        var wikipediaUrl = "";
        var wikiLinks = document.querySelectorAll('a[href*="wikipedia.org"]');
        if (wikiLinks.length > 0) {
            wikipediaUrl = wikiLinks[0].href;
        }
        
        // Prepare the result object - ONLY include non-empty values
        var result = {
            "name": name,
            "musicbrainzId": musicbrainzId,
            "url": url
        };
        
        // Only add optional fields if they have values
        if (biography) {
            result.biography = biography;
        }
        
        if (birthDate) {
            result.birthDate = birthDate;
        }
        
        if (deathDate) {
            result.deathDate = deathDate;
        }
        
        if (instruments.length > 0) {
            result.instruments = instruments;
        }
        
        if (wikipediaUrl) {
            result.wikipediaUrl = wikipediaUrl;
        }
        
        // Return results to the extension
        arguments.completionFunction(result);
    },
    
    extractSongData: function(arguments, url) {
        // Extract MusicBrainz work ID from URL
        var mbidMatch = url.match(/\/work\/([a-f0-9\-]+)/);
        var musicbrainzId = mbidMatch ? mbidMatch[1] : "";
        
        // Extract work title - try multiple selectors
        var title = "";
        
        // Try 1: Link inside h1 (some pages may have this)
        var titleElement = document.querySelector('h1 a[href*="/work/"]');
        if (titleElement) {
            title = titleElement.textContent.trim();
        }
        
        // Try 2: Just the h1 text content (most common)
        if (!title) {
            var h1Element = document.querySelector('h1');
            if (h1Element) {
                // Get only the direct text content, not nested elements
                title = h1Element.textContent.trim();
            }
        }
        
        // Try 3: Get from page title as fallback
        if (!title) {
            var pageTitle = document.title;
            // Remove " - MusicBrainz" from the end if present
            title = pageTitle.replace(/\s*-\s*MusicBrainz\s*$/, '').trim();
        }
        
        // Extract composer(s) - try multiple selectors
        var composers = [];
        
        // Look for composer or writer in the details list
        var composerElements = document.querySelectorAll('dd.writer a[href*="/artist/"], dd.composer a[href*="/artist/"]');
        composerElements.forEach(function(element) {
            var composerName = element.textContent.trim();
            if (composerName && composers.indexOf(composerName) === -1) {
                composers.push(composerName);
            }
        });
        
        // Extract type (song, instrumental, etc.)
        var workType = "";
        var typeElement = document.querySelector('dd.type');
        if (typeElement) {
            workType = typeElement.textContent.trim();
        }
        
        // Extract key
        var musicalKey = "";
        var keyElement = document.querySelector('dd.key');
        if (keyElement) {
            musicalKey = keyElement.textContent.trim();
        }
        
        // Extract ISWC (International Standard Musical Work Code)
        var iswc = "";
        var iswcElement = document.querySelector('dd.iswc');
        if (iswcElement) {
            iswc = iswcElement.textContent.trim();
        }
        
        // Extract language
        var language = "";
        var langElement = document.querySelector('dd.language a');
        if (langElement) {
            language = langElement.textContent.trim();
        }
        
        // Extract annotation/description if available
        var annotation = "";
        var annotationElement = document.querySelector('.annotation');
        if (annotationElement) {
            var clone = annotationElement.cloneNode(true);
            var buttons = clone.querySelectorAll('button, a.toggle');
            buttons.forEach(function(btn) { btn.remove(); });
            annotation = clone.textContent.trim();
        }
        
        // Extract Wikipedia URL from external links
        var wikipediaUrl = "";
        var wikiLinks = document.querySelectorAll('a[href*="wikipedia.org"]');
        if (wikiLinks.length > 0) {
            wikipediaUrl = wikiLinks[0].href;
        }
        
        // Prepare the result object - ONLY include non-empty values
        var result = {
            "title": title,
            "musicbrainzId": musicbrainzId,
            "url": url
        };
        
        // Only add optional fields if they have values
        if (composers.length > 0) {
            result.composers = composers;
        }
        
        if (workType) {
            result.workType = workType;
        }
        
        if (musicalKey) {
            result.key = musicalKey;
        }
        
        if (iswc) {
            result.iswc = iswc;
        }
        
        if (language) {
            result.language = language;
        }
        
        if (annotation) {
            result.annotation = annotation;
        }
        
        if (wikipediaUrl) {
            result.wikipediaUrl = wikipediaUrl;
        }
        
        // Return results to the extension
        arguments.completionFunction(result);
    },

    extractYouTubeData: function(arguments, url) {
        // Extract YouTube video ID from URL
        var videoId = "";

        // Handle youtube.com/watch?v=VIDEO_ID format
        var watchMatch = url.match(/[?&]v=([^&]+)/);
        if (watchMatch) {
            videoId = watchMatch[1];
        }

        // Handle youtu.be/VIDEO_ID format
        if (!videoId) {
            var shortMatch = url.match(/youtu\.be\/([^?&]+)/);
            if (shortMatch) {
                videoId = shortMatch[1];
            }
        }

        // Extract video title from page
        var title = "";

        // Try the main title element (works on most YouTube pages)
        var titleElement = document.querySelector('h1.ytd-watch-metadata yt-formatted-string');
        if (titleElement) {
            title = titleElement.textContent.trim();
        }

        // Fallback to meta title
        if (!title) {
            var metaTitle = document.querySelector('meta[name="title"]');
            if (metaTitle) {
                title = metaTitle.getAttribute('content') || '';
            }
        }

        // Fallback to document title
        if (!title) {
            title = document.title.replace(/ - YouTube$/, '').trim();
        }

        // Extract channel name
        var channelName = "";
        var channelElement = document.querySelector('#owner #channel-name yt-formatted-string a');
        if (channelElement) {
            channelName = channelElement.textContent.trim();
        }

        // Fallback for channel name
        if (!channelName) {
            var ownerElement = document.querySelector('ytd-channel-name yt-formatted-string a');
            if (ownerElement) {
                channelName = ownerElement.textContent.trim();
            }
        }

        // Extract video description (first 500 chars)
        var description = "";
        var descElement = document.querySelector('#description-inline-expander yt-attributed-string');
        if (descElement) {
            description = descElement.textContent.trim().substring(0, 500);
        }

        // Prepare the result object
        var result = {
            "pageType": "youtube",
            "videoId": videoId,
            "title": title,
            "url": url
        };

        if (channelName) {
            result.channelName = channelName;
        }

        if (description) {
            result.description = description;
        }

        // Return results to the extension
        arguments.completionFunction(result);
    },

    // This is called before the run function to allow page finalization
    finalize: function(arguments) {
        // No finalization needed
    }
};

// Create the instance
var ExtensionPreprocessingJS = new ExtractMusicBrainzData;
