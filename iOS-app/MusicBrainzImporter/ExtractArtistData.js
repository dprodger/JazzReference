//
//  ExtractArtistData.js
//  MusicBrainzImporter
//
//  JavaScript to extract artist information from MusicBrainz artist pages
//

var ExtractArtistData = function() {};

ExtractArtistData.prototype = {
    
    run: function(arguments) {
        // Ensure we're on a MusicBrainz artist page
        var url = document.location.href;
        
        if (!url.includes('musicbrainz.org/artist/')) {
            arguments.completionFunction({
                "error": "Not a MusicBrainz artist page"
            });
            return;
        }
        
        // Extract MusicBrainz ID from URL
        // URL format: https://musicbrainz.org/artist/{mbid}
        var mbidMatch = url.match(/\/artist\/([a-f0-9\-]{36})/);
        var musicbrainzId = mbidMatch ? mbidMatch[1] : "";
        
        // Extract artist name
        var name = "";
        var nameElement = document.querySelector('h1 a[href^="/artist/"]');
        if (nameElement) {
            name = nameElement.textContent.trim();
        }
        
        // If no name found, try alternative selector
        if (!name) {
            var h1 = document.querySelector('h1.page-header');
            if (h1) {
                name = h1.textContent.trim();
            }
        }
        
        // Extract biography/annotation
        var biography = "";
        var bioElement = document.querySelector('.wikipedia-extract-body');
        if (bioElement) {
            biography = bioElement.textContent.trim();
        } else {
            // Try annotation section
            var annotationElement = document.querySelector('.annotation');
            if (annotationElement) {
                biography = annotationElement.textContent.trim();
            }
        }
        
        // Extract dates
        var birthDate = "";
        var deathDate = "";
        
        // Look for life-span in the details section
        var lifeSpanElement = document.querySelector('dd.life-span');
        if (lifeSpanElement) {
            var lifeSpanText = lifeSpanElement.textContent;
            
            // Try to extract dates (format: "YYYY-MM-DD – YYYY-MM-DD" or "YYYY – YYYY")
            var dateMatch = lifeSpanText.match(/(\d{4}(?:-\d{2}-\d{2})?)\s*[–-]\s*(\d{4}(?:-\d{2}-\d{2})?)/);
            if (dateMatch) {
                birthDate = dateMatch[1];
                deathDate = dateMatch[2];
            } else {
                // Just birth date (still alive)
                var birthMatch = lifeSpanText.match(/(\d{4}(?:-\d{2}-\d{2})?)/);
                if (birthMatch) {
                    birthDate = birthMatch[1];
                }
            }
        }
        
        // Extract instruments
        var instruments = [];
        var instrumentElements = document.querySelectorAll('dd.instrument a[href^="/instrument/"]');
        instrumentElements.forEach(function(element) {
            var instrument = element.textContent.trim();
            if (instrument && !instruments.includes(instrument)) {
                instruments.push(instrument);
            }
        });
        
        // Extract Wikipedia URL if available
        var wikipediaUrl = "";
        var wikiLink = document.querySelector('a[href*="wikipedia.org"]');
        if (wikiLink) {
            wikipediaUrl = wikiLink.href;
        }
        
        // Extract type (person, group, etc.)
        var artistType = "";
        var typeElement = document.querySelector('dd.type');
        if (typeElement) {
            artistType = typeElement.textContent.trim();
        }
        
        // Extract gender (if person)
        var gender = "";
        var genderElement = document.querySelector('dd.gender');
        if (genderElement) {
            gender = genderElement.textContent.trim();
        }
        
        // Extract country/area
        var area = "";
        var areaElement = document.querySelector('dd.begin-area a, dd.area a');
        if (areaElement) {
            area = areaElement.textContent.trim();
        }
        
        // Prepare the result object - ONLY include non-empty values
        // This prevents null/undefined serialization issues
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
        
        if (artistType) {
            result.artistType = artistType;
        }
        
        if (gender) {
            result.gender = gender;
        }
        
        if (area) {
            result.area = area;
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
var ExtensionPreprocessingJS = new ExtractArtistData;
