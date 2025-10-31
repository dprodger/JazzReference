// ExtractMusicBrainzData.js
// Combined JavaScript preprocessing file for extracting both artist and song/work data from MusicBrainz
// This runs in the Safari extension context before the share sheet appears

var ExtractMusicBrainzData = function() {};

ExtractMusicBrainzData.prototype = {
    run: function(arguments) {
        // DEBUG: Log that JavaScript is running
        console.log("🟢 JavaScript preprocessing started!");
        console.log("URL: " + document.location.href);
        
        // Extract the URL to determine page type
        var url = document.location.href;
        
        // Check if this is a MusicBrainz page
        if (!url.includes('musicbrainz.org')) {
            arguments.completionFunction({
                "error": "This extension only works on MusicBrainz pages",
                "url": url
            });
            return;
        }
        
        // Determine page type and extract appropriate data
        if (url.includes('musicbrainz.org/artist/')) {
            this.extractArtistData(arguments, url);
        } else if (url.includes('musicbrainz.org/work/')) {
            this.extractSongData(arguments, url);
        } else {
            arguments.completionFunction({
                "error": "This extension only works on MusicBrainz artist or work pages",
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
            birthDate = birthElement.textContent.trim();
        }
        
        // Extract death date
        var deathDate = "";
        var deathElement = document.querySelector('dd.end-date');
        if (deathElement) {
            deathDate = deathElement.textContent.trim();
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
        
        // Extract work title
        var title = "";
        // Try multiple selectors for robustness
        var titleElement = document.querySelector('h1 a[href*="/work/"]');
        if (titleElement) {
            title = titleElement.textContent.trim();
        }

        // Try 2: Just the h1 text content (most common)
        if (!title) {
            var h1Element = document.querySelector('h1');
            if (h1Element) {
                title = h1Element.textContent.trim();
            }
        }

        // Try 3: Get from page title as fallback
        if (!title) {
            var pageTitle = document.title;
            title = pageTitle.replace(/\s*-\s*MusicBrainz\s*$/, '').trim();
        }
        // Extract composer(s)
        var composers = [];
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
    
    // This is called before the run function to allow page finalization
    finalize: function(arguments) {
        // No finalization needed
    }
};

// Create the instance
var ExtensionPreprocessingJS = new ExtractMusicBrainzData;
