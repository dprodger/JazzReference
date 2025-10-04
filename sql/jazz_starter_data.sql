-- ============================================================================
-- Jazz Reference Application - Starter Data SQL Script
-- ============================================================================
-- This script populates the database with jazz standards from Ted Gioia's
-- "The Jazz Standards: A Guide to the Repertoire" and additional metadata
-- ============================================================================

BEGIN;

-- ============================================================================
-- PERFORMERS
-- ============================================================================

-- Insert famous jazz performers
INSERT INTO performers (name, biography, birth_date, death_date, external_links) VALUES
('Miles Davis', 'Legendary trumpeter and bandleader, pioneer of cool jazz, hard bop, and jazz fusion. Known for albums like Kind of Blue, Bitches Brew, and Birth of the Cool.', '1926-05-26', '1991-09-28', '{"wikipedia": "https://en.wikipedia.org/wiki/Miles_Davis"}'),
('John Coltrane', 'Influential tenor and soprano saxophonist, pioneer of modal jazz and free jazz. Known for A Love Supreme and Giant Steps.', '1926-09-23', '1967-07-17', '{"wikipedia": "https://en.wikipedia.org/wiki/John_Coltrane"}'),
('Bill Evans', 'Innovative jazz pianist known for his lyrical playing and harmonic sophistication. Key member of the Kind of Blue sessions.', '1929-08-16', '1980-09-15', '{"wikipedia": "https://en.wikipedia.org/wiki/Bill_Evans"}'),
('Cannonball Adderley', 'Alto saxophonist known for his soulful, bluesy style and work with Miles Davis.', '1928-09-15', '1975-08-08', '{"wikipedia": "https://en.wikipedia.org/wiki/Cannonball_Adderley"}'),
('Paul Chambers', 'Influential jazz double bassist, member of Miles Davis Quintet and Sextet.', '1935-04-22', '1969-01-04', '{"wikipedia": "https://en.wikipedia.org/wiki/Paul_Chambers"}'),
('Jimmy Cobb', 'Renowned jazz drummer, best known for his work on Kind of Blue.', '1929-01-20', '2020-05-24', '{"wikipedia": "https://en.wikipedia.org/wiki/Jimmy_Cobb"}'),
('Chet Baker', 'Trumpeter and vocalist, icon of cool jazz known for his lyrical playing and intimate vocal style.', '1929-12-23', '1988-05-13', '{"wikipedia": "https://en.wikipedia.org/wiki/Chet_Baker"}'),
('Gerry Mulligan', 'Baritone saxophonist and arranger, pioneer of cool jazz and the pianoless quartet.', '1927-04-06', '1996-01-20', '{"wikipedia": "https://en.wikipedia.org/wiki/Gerry_Mulligan"}'),
('Frank Sinatra', 'Legendary vocalist who helped popularize many jazz standards with his interpretations.', '1915-12-12', '1998-05-14', '{"wikipedia": "https://en.wikipedia.org/wiki/Frank_Sinatra"}'),
('Ella Fitzgerald', 'First Lady of Song, renowned for her vocal range, clarity, and scat singing ability.', '1917-04-25', '1996-06-15', '{"wikipedia": "https://en.wikipedia.org/wiki/Ella_Fitzgerald"}'),
('Charlie Parker', 'Revolutionary alto saxophonist, pioneer of bebop and one of the most influential jazz musicians.', '1920-08-29', '1955-03-12', '{"wikipedia": "https://en.wikipedia.org/wiki/Charlie_Parker"}'),
('Dizzy Gillespie', 'Trumpeter, bandleader, and composer, co-founder of bebop.', '1917-10-21', '1993-01-06', '{"wikipedia": "https://en.wikipedia.org/wiki/Dizzy_Gillespie"}'),
('Wynton Kelly', 'Hard bop pianist known for his bluesy, swinging style and work with Miles Davis.', '1931-12-02', '1971-04-12', '{"wikipedia": "https://en.wikipedia.org/wiki/Wynton_Kelly"}'),
('Thelonious Monk', 'Innovative pianist and composer known for his unique improvisational style and compositions.', '1917-10-10', '1982-02-17', '{"wikipedia": "https://en.wikipedia.org/wiki/Thelonious_Monk"}'),
('Duke Ellington', 'Composer, pianist, and bandleader, one of the most important figures in jazz history.', '1899-04-29', '1974-05-24', '{"wikipedia": "https://en.wikipedia.org/wiki/Duke_Ellington"}');

-- ============================================================================
-- SONGS - Detailed Entries (with composer and reference information)
-- ============================================================================

INSERT INTO songs (title, composer, structure, external_references) VALUES
('All the Things You Are', 'Jerome Kern and Oscar Hammerstein II', '36-bar AABA form with modulations through multiple keys (Ab-C-Eb-G-E-Ab). Known for sophisticated harmonic progressions.', '{"wikipedia": "https://en.wikipedia.org/wiki/All_the_Things_You_Are", "notes": "From the musical Very Warm for May (1939). One of the most recorded jazz standards."}'),

('Autumn Leaves', 'Joseph Kosma (music), Jacques Prévert (French lyrics), Johnny Mercer (English lyrics)', '32-bar AABC form. Originally titled Les Feuilles mortes. Popular for teaching ii-V-I progressions.', '{"wikipedia": "https://en.wikipedia.org/wiki/Autumn_Leaves_(1945_song)", "notes": "From the 1946 film Les Portes de la nuit. The most important non-American jazz standard."}'),

('My Funny Valentine', 'Richard Rodgers (music) and Lorenz Hart (lyrics)', '32-bar AABA form in C minor. Features the classic minor cliché progression.', '{"wikipedia": "https://en.wikipedia.org/wiki/My_Funny_Valentine", "notes": "From the 1937 musical Babes in Arms. Recorded over 1300 times by 600+ artists."}'),

('So What', 'Miles Davis', 'Modal jazz composition with 32-bar AABA form. Based on Dorian mode.', '{"wikipedia": "https://en.wikipedia.org/wiki/So_What_(Miles_Davis_composition)", "notes": "Opening track of Kind of Blue (1959). Landmark modal jazz composition."}'),

('Blue in Green', 'Miles Davis (disputed authorship with Bill Evans)', '10-bar circular form with 4-bar introduction. Modal ballad.', '{"wikipedia": "https://en.wikipedia.org/wiki/Blue_in_Green", "notes": "From Kind of Blue. Authorship disputed between Davis and Evans."}'),

('All Blues', 'Miles Davis', '12-bar blues in 6/8 time. Modal approach to blues form.', '{"wikipedia": "https://en.wikipedia.org/wiki/All_Blues", "notes": "From Kind of Blue (1959). Combines traditional blues with modal jazz."}');

-- ============================================================================
-- SONGS - Basic Entries (from Ted Gioia's Jazz Standards list)
-- ============================================================================

INSERT INTO songs (title, composer) VALUES
('After You''ve Gone', 'Turner Layton and Henry Creamer'),
('Ain''t Misbehavin''', 'Fats Waller and Harry Brooks'),
('Airegin', 'Sonny Rollins'),
('Alfie', 'Burt Bacharach and Hal David'),
('All of Me', 'Gerald Marks and Seymour Simons'),
('All of You', 'Cole Porter'),
('Almost Like Being in Love', 'Frederick Loewe and Alan Jay Lerner'),
('Alone Together', 'Arthur Schwartz and Howard Dietz'),
('Along Came Betty', 'Benny Golson'),
('Angel Eyes', 'Matt Dennis and Earl Brent'),
('April in Paris', 'Vernon Duke and E. Y. Harburg'),
('Autumn in New York', 'Vernon Duke'),
('Bags'' Groove', 'Milt Jackson'),
('Basin Street Blues', 'Spencer Williams'),
('Beale Street Blues', 'W. C. Handy'),
('Bemsha Swing', 'Thelonious Monk and Denzil Best'),
('Billie''s Bounce', 'Charlie Parker'),
('Birdland', 'Joe Zawinul'),
('Blue Bossa', 'Kenny Dorham'),
('Blue Monk', 'Thelonious Monk'),
('Blue Moon', 'Richard Rodgers and Lorenz Hart'),
('Blue Skies', 'Irving Berlin'),
('Blues in the Night', 'Harold Arlen and Johnny Mercer'),
('Bluesette', 'Toots Thielemans and Norman Gimbel'),
('Body and Soul', 'Johnny Green, Edward Heyman, Robert Sour, and Frank Eyton'),
('But Beautiful', 'Jimmy Van Heusen and Johnny Burke'),
('But Not for Me', 'George Gershwin and Ira Gershwin'),
('Bye Bye Blackbird', 'Ray Henderson and Mort Dixon'),
('C Jam Blues', 'Duke Ellington'),
('Cantaloupe Island', 'Herbie Hancock'),
('Caravan', 'Juan Tizol and Duke Ellington'),
('Chelsea Bridge', 'Billy Strayhorn'),
('Cherokee', 'Ray Noble'),
('A Child Is Born', 'Thad Jones'),
('Come Rain or Come Shine', 'Harold Arlen and Johnny Mercer'),
('Come Sunday', 'Duke Ellington'),
('Con Alma', 'Dizzy Gillespie'),
('Confirmation', 'Charlie Parker'),
('Corcovado', 'Antonio Carlos Jobim'),
('Cotton Tail', 'Duke Ellington'),
('Darn That Dream', 'Jimmy Van Heusen and Eddie DeLange'),
('Days of Wine and Roses', 'Henry Mancini and Johnny Mercer'),
('Desafinado', 'Antonio Carlos Jobim and Newton Mendonça'),
('Dinah', 'Harry Akst and Sam M. Lewis'),
('Django', 'John Lewis'),
('Do Nothin'' Till You Hear from Me', 'Duke Ellington and Bob Russell'),
('Do You Know What It Means to Miss New Orleans', 'Louis Alter and Eddie DeLange'),
('Dolphin Dance', 'Herbie Hancock'),
('Donna Lee', 'Charlie Parker'),
('Don''t Blame Me', 'Jimmy McHugh and Dorothy Fields'),
('Don''t Get Around Much Anymore', 'Duke Ellington and Bob Russell'),
('East of the Sun (and West of the Moon)', 'Brooks Bowman'),
('Easy Living', 'Ralph Rainger and Leo Robin'),
('Easy to Love', 'Cole Porter'),
('Embraceable You', 'George Gershwin and Ira Gershwin'),
('Emily', 'Johnny Mandel and Johnny Mercer'),
('Epistrophy', 'Thelonious Monk and Kenny Clarke'),
('Everything Happens to Me', 'Matt Dennis and Tom Adair'),
('Evidence', 'Thelonious Monk'),
('Ev''ry Time We Say Goodbye', 'Cole Porter'),
('Exactly Like You', 'Jimmy McHugh and Dorothy Fields'),
('Falling in Love with Love', 'Richard Rodgers and Lorenz Hart'),
('Fascinating Rhythm', 'George Gershwin and Ira Gershwin'),
('Fly Me to the Moon', 'Bart Howard'),
('A Foggy Day', 'George Gershwin and Ira Gershwin'),
('Footprints', 'Wayne Shorter'),
('Gee, Baby, Ain''t I Good to You?', 'Andy Razaf and Don Redman'),
('Georgia on My Mind', 'Hoagy Carmichael and Stuart Gorrell'),
('Ghost of a Chance', 'Victor Young, Ned Washington, and Bing Crosby'),
('Giant Steps', 'John Coltrane'),
('The Girl from Ipanema', 'Antonio Carlos Jobim and Vinicius de Moraes'),
('God Bless the Child', 'Billie Holiday and Arthur Herzog Jr.'),
('Gone with the Wind', 'Allie Wrubel and Herb Magidson'),
('Good Morning Heartache', 'Irene Higginbotham, Ervin Drake, and Dan Fisher'),
('Goodbye Pork Pie Hat', 'Charles Mingus'),
('Groovin'' High', 'Dizzy Gillespie'),
('Have You Met Miss Jones?', 'Richard Rodgers and Lorenz Hart'),
('Here''s That Rainy Day', 'Jimmy Van Heusen and Johnny Burke'),
('Honeysuckle Rose', 'Fats Waller and Andy Razaf'),
('Hot House', 'Tadd Dameron'),
('How Deep Is the Ocean?', 'Irving Berlin'),
('How High the Moon', 'Morgan Lewis and Nancy Hamilton'),
('How Insensitive', 'Antonio Carlos Jobim and Vinicius de Moraes'),
('How Long Has This Been Going On?', 'George Gershwin and Ira Gershwin'),
('I Can''t Get Started', 'Vernon Duke and Ira Gershwin'),
('I Can''t Give You Anything but Love', 'Jimmy McHugh and Dorothy Fields'),
('I Cover the Waterfront', 'Johnny Green and Edward Heyman'),
('I Didn''t Know What Time It Was', 'Richard Rodgers and Lorenz Hart'),
('I Fall in Love Too Easily', 'Jule Styne and Sammy Cahn'),
('I Got It Bad (and That Ain''t Good)', 'Duke Ellington and Paul Francis Webster'),
('I Got Rhythm', 'George Gershwin and Ira Gershwin'),
('I Hear a Rhapsody', 'George Fragos, Jack Baker, and Dick Gasparre'),
('I Let a Song Go Out of My Heart', 'Duke Ellington, Henry Nemo, John Redmond, and Irving Mills'),
('I Love You', 'Cole Porter'),
('I Mean You', 'Thelonious Monk'),
('I Only Have Eyes for You', 'Harry Warren and Al Dubin'),
('I Remember Clifford', 'Benny Golson'),
('I Should Care', 'Axel Stordahl, Paul Weston, and Sammy Cahn'),
('I Surrender, Dear', 'Harry Barris and Gordon Clifford'),
('I Thought about You', 'Jimmy Van Heusen and Johnny Mercer'),
('I Want to Be Happy', 'Vincent Youmans and Irving Caesar'),
('If I Should Lose You', 'Ralph Rainger and Leo Robin'),
('If You Could See Me Now', 'Tadd Dameron and Carl Sigman'),
('I''ll Remember April', 'Gene de Paul, Patricia Johnston, and Don Raye'),
('I''m in the Mood for Love', 'Jimmy McHugh and Dorothy Fields'),
('Impressions', 'John Coltrane'),
('In a Mellow Tone', 'Duke Ellington'),
('In a Sentimental Mood', 'Duke Ellington'),
('In Your Own Sweet Way', 'Dave Brubeck'),
('Indiana', 'James F. Hanley and Ballard MacDonald'),
('Invitation', 'Bronisław Kaper and Paul Francis Webster'),
('It Could Happen to You', 'Jimmy Van Heusen and Johnny Burke'),
('It Don''t Mean a Thing (If It Ain''t Got That Swing)', 'Duke Ellington and Irving Mills'),
('It Had to Be You', 'Isham Jones and Gus Kahn'),
('It Might as Well Be Spring', 'Richard Rodgers and Oscar Hammerstein II'),
('It Never Entered My Mind', 'Richard Rodgers and Lorenz Hart'),
('I''ve Found a New Baby', 'Jack Palmer and Spencer Williams'),
('The Jitterbug Waltz', 'Fats Waller'),
('Joy Spring', 'Clifford Brown'),
('Just Friends', 'John Klenner and Sam M. Lewis'),
('Just One of Those Things', 'Cole Porter'),
('Just You, Just Me', 'Jesse Greer and Raymond Klages'),
('King Porter Stomp', 'Jelly Roll Morton'),
('Lady Bird', 'Tadd Dameron'),
('The Lady Is a Tramp', 'Richard Rodgers and Lorenz Hart'),
('Lament', 'J. J. Johnson'),
('Laura', 'David Raksin and Johnny Mercer'),
('Lester Leaps In', 'Lester Young'),
('Like Someone in Love', 'Jimmy Van Heusen and Johnny Burke'),
('Limehouse Blues', 'Philip Braham and Douglas Furber'),
('Liza', 'George Gershwin and Ira Gershwin'),
('Lonely Woman', 'Ornette Coleman'),
('Lotus Blossom', 'Billy Strayhorn'),
('Love for Sale', 'Cole Porter'),
('Love Is Here to Stay', 'George Gershwin and Ira Gershwin'),
('Lover', 'Richard Rodgers and Lorenz Hart'),
('Lover, Come Back to Me', 'Sigmund Romberg and Oscar Hammerstein II'),
('Lover Man', 'Jimmy Davis, Roger Ramirez, and Jimmy Sherman'),
('Lullaby of Birdland', 'George Shearing and George David Weiss'),
('Lush Life', 'Billy Strayhorn'),
('Mack the Knife', 'Kurt Weill and Bertolt Brecht'),
('Maiden Voyage', 'Herbie Hancock'),
('The Man I Love', 'George Gershwin and Ira Gershwin'),
('Manhã de Carnaval', 'Luiz Bonfá and Antônio Maria'),
('Mean to Me', 'Fred E. Ahlert and Roy Turk'),
('Meditation', 'Antonio Carlos Jobim and Newton Mendonça'),
('Memories of You', 'Eubie Blake and Andy Razaf'),
('Milestones', 'Miles Davis'),
('Misterioso', 'Thelonious Monk'),
('Misty', 'Erroll Garner and Johnny Burke'),
('Moanin''', 'Bobby Timmons'),
('Moment''s Notice', 'John Coltrane'),
('Mood Indigo', 'Duke Ellington, Barney Bigard, and Irving Mills'),
('Moonlight in Vermont', 'Karl Suessdorf and John Blackburn'),
('Moose the Mooche', 'Charlie Parker'),
('More Than You Know', 'Vincent Youmans, Billy Rose, and Edward Eliscu'),
('Muskrat Ramble', 'Kid Ory and Ray Gilbert'),
('My Favorite Things', 'Richard Rodgers and Oscar Hammerstein II'),
('My Foolish Heart', 'Victor Young and Ned Washington'),
('My Heart Stood Still', 'Richard Rodgers and Lorenz Hart'),
('My Old Flame', 'Arthur Johnston and Sam Coslow'),
('My One and Only Love', 'Guy Wood and Robert Mellin'),
('My Romance', 'Richard Rodgers and Lorenz Hart'),
('Naima', 'John Coltrane'),
('Nardis', 'Miles Davis'),
('Nature Boy', 'Eden Ahbez'),
('The Nearness of You', 'Hoagy Carmichael and Ned Washington'),
('Nice Work If You Can Get It', 'George Gershwin and Ira Gershwin'),
('Night and Day', 'Cole Porter'),
('Night in Tunisia', 'Dizzy Gillespie and Frank Paparelli'),
('Night Train', 'Jimmy Forrest'),
('Now''s the Time', 'Charlie Parker'),
('Nuages', 'Django Reinhardt'),
('Oh, Lady Be Good!', 'George Gershwin and Ira Gershwin'),
('Old Folks', 'Willard Robison and Dedette Lee Hill'),
('Oleo', 'Sonny Rollins'),
('On a Clear Day', 'Burton Lane and Alan Jay Lerner'),
('On Green Dolphin Street', 'Bronisław Kaper and Ned Washington'),
('On the Sunny Side of the Street', 'Jimmy McHugh and Dorothy Fields'),
('Once I Loved', 'Antonio Carlos Jobim and Vinicius de Moraes'),
('One Note Samba', 'Antonio Carlos Jobim and Newton Mendonça'),
('One o''Clock Jump', 'Count Basie'),
('Ornithology', 'Charlie Parker and Benny Harris'),
('Out of Nowhere', 'Johnny Green and Edward Heyman'),
('Over the Rainbow', 'Harold Arlen and E. Y. Harburg'),
('Peace', 'Horace Silver'),
('The Peacocks', 'Jimmy Rowles'),
('Pennies from Heaven', 'Arthur Johnston and Johnny Burke'),
('Perdido', 'Juan Tizol'),
('Poinciana', 'Nat Simon and Buddy Bernier'),
('Polka Dots and Moonbeams', 'Jimmy Van Heusen and Johnny Burke'),
('Prelude to a Kiss', 'Duke Ellington and Irving Gordon'),
('Rhythm-a-ning', 'Thelonious Monk'),
('''Round Midnight', 'Thelonious Monk, Cootie Williams, and Bernie Hanighen'),
('Royal Garden Blues', 'Clarence Williams and Spencer Williams'),
('Ruby, My Dear', 'Thelonious Monk'),
('St. James Infirmary Blues', 'Traditional'),
('St. Louis Blues', 'W. C. Handy'),
('St. Thomas', 'Sonny Rollins'),
('Satin Doll', 'Duke Ellington and Billy Strayhorn'),
('Scrapple from the Apple', 'Charlie Parker'),
('Secret Love', 'Sammy Fain and Paul Francis Webster'),
('The Shadow of Your Smile', 'Johnny Mandel and Paul Francis Webster'),
('Skylark', 'Hoagy Carmichael and Johnny Mercer'),
('Smile', 'Charles Chaplin, John Turner, and Geoffrey Parsons'),
('Smoke Gets in Your Eyes', 'Jerome Kern and Otto Harbach'),
('Softly, as in a Morning Sunrise', 'Sigmund Romberg and Oscar Hammerstein II'),
('Solar', 'Miles Davis'),
('Solitude', 'Duke Ellington, Eddie DeLange, and Irving Mills'),
('Some of These Days', 'Shelton Brooks'),
('Someday My Prince Will Come', 'Frank Churchill and Larry Morey'),
('Someone to Watch over Me', 'George Gershwin and Ira Gershwin'),
('Song for My Father', 'Horace Silver'),
('The Song Is You', 'Jerome Kern and Oscar Hammerstein II'),
('Sophisticated Lady', 'Duke Ellington, Irving Mills, and Mitchell Parish'),
('Soul Eyes', 'Mal Waldron'),
('Speak Low', 'Kurt Weill and Ogden Nash'),
('Spring Can Really Hang You Up the Most', 'Tommy Wolf and Fran Landesman'),
('Spring Is Here', 'Richard Rodgers and Lorenz Hart'),
('Star Dust', 'Hoagy Carmichael and Mitchell Parish'),
('Star Eyes', 'Gene de Paul and Don Raye'),
('Stella by Starlight', 'Victor Young and Ned Washington'),
('Stolen Moments', 'Oliver Nelson'),
('Stompin'' at the Savoy', 'Benny Goodman, Chick Webb, Edgar Sampson, and Andy Razaf'),
('Stormy Weather', 'Harold Arlen and Ted Koehler'),
('Straight, No Chaser', 'Thelonious Monk'),
('Struttin'' with Some Barbecue', 'Lil Hardin Armstrong'),
('Summertime', 'George Gershwin and DuBose Heyward'),
('Sweet Georgia Brown', 'Ben Bernie, Maceo Pinkard, and Kenneth Casey'),
('''S Wonderful', 'George Gershwin and Ira Gershwin'),
('Take Five', 'Paul Desmond'),
('Take the A Train', 'Billy Strayhorn'),
('Tea for Two', 'Vincent Youmans and Irving Caesar'),
('Tenderly', 'Jack Lawrence and Walter Gross'),
('There Is No Greater Love', 'Isham Jones and Marty Symes'),
('There Will Never Be Another You', 'Harry Warren and Mack Gordon'),
('These Foolish Things (Remind Me of You)', 'Jack Strachey, Harry Link, and Holt Marvell'),
('They Can''t Take That Away from Me', 'George Gershwin and Ira Gershwin'),
('Things Ain''t What They Used to Be', 'Mercer Ellington'),
('Tiger Rag', 'Nick LaRocca'),
('Time after Time', 'Jule Styne and Sammy Cahn'),
('Tin Roof Blues', 'New Orleans Rhythm Kings'),
('The Very Thought of You', 'Ray Noble'),
('Waltz for Debby', 'Bill Evans and Gene Lees'),
('Watermelon Man', 'Herbie Hancock'),
('Wave', 'Antonio Carlos Jobim'),
('The Way You Look Tonight', 'Jerome Kern and Dorothy Fields'),
('Well, You Needn''t', 'Thelonious Monk'),
('What Is This Thing Called Love?', 'Cole Porter'),
('What''s New?', 'Bob Haggart and Johnny Burke'),
('When the Saints Go Marching In', 'Traditional'),
('Whisper Not', 'Benny Golson'),
('Who Can I Turn To?', 'Leslie Bricusse and Anthony Newley'),
('Willow Weep for Me', 'Ann Ronell'),
('Yardbird Suite', 'Charlie Parker'),
('Yesterdays', 'Jerome Kern and Otto Harbach'),
('You Don''t Know What Love Is', 'Gene de Paul and Don Raye'),
('You Go to My Head', 'J. Fred Coots and Haven Gillespie'),
('You Stepped Out of a Dream', 'Nacio Herb Brown and Gus Kahn'),
('You''d Be So Nice to Come Home To', 'Cole Porter');

-- ============================================================================
-- RECORDINGS - Canonical Recordings
-- ============================================================================

-- Get instrument IDs for use in recording_performers
DO $$
DECLARE
    trumpet_id UUID;
    alto_sax_id UUID;
    tenor_sax_id UUID;
    piano_id UUID;
    bass_id UUID;
    drums_id UUID;
    vocals_id UUID;
    baritone_sax_id UUID;
BEGIN
    SELECT id INTO trumpet_id FROM instruments WHERE name = 'Trumpet';
    SELECT id INTO alto_sax_id FROM instruments WHERE name = 'Alto Saxophone';
    SELECT id INTO tenor_sax_id FROM instruments WHERE name = 'Tenor Saxophone';
    SELECT id INTO piano_id FROM instruments WHERE name = 'Piano';
    SELECT id INTO bass_id FROM instruments WHERE name = 'Bass';
    SELECT id INTO drums_id FROM instruments WHERE name = 'Drums';
    SELECT id INTO vocals_id FROM instruments WHERE name = 'Vocals';
    SELECT id INTO baritone_sax_id FROM instruments WHERE name = 'Baritone Saxophone';

    -- Kind of Blue - So What
    INSERT INTO recordings (song_id, album_title, recording_date, recording_year, label, spotify_url, is_canonical, notes)
    SELECT id, 'Kind of Blue', '1959-03-02', 1959, 'Columbia Records', 
           'https://open.spotify.com/track/3nWbqm5VG9C5zCZvRWJ9gN', 
           true,
           'Recorded at Columbia 30th Street Studio. First track on one of the most influential jazz albums of all time.'
    FROM songs WHERE title = 'So What';

    -- Add performers for So What
    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, trumpet_id, 'leader'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%First track%' 
    AND p.name = 'Miles Davis';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, alto_sax_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%First track%' 
    AND p.name = 'Cannonball Adderley';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, tenor_sax_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%First track%' 
    AND p.name = 'John Coltrane';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, piano_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%First track%' 
    AND p.name = 'Bill Evans';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, bass_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%First track%' 
    AND p.name = 'Paul Chambers';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, drums_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%First track%' 
    AND p.name = 'Jimmy Cobb';

    -- Kind of Blue - Blue in Green
    INSERT INTO recordings (song_id, album_title, recording_date, recording_year, label, is_canonical, notes)
    SELECT id, 'Kind of Blue', '1959-03-02', 1959, 'Columbia Records',
           true,
           'Lyrical modal ballad. Take 5 was the only complete version recorded.'
    FROM songs WHERE title = 'Blue in Green';

    -- Add performers for Blue in Green (same as So What except no Cannonball)
    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, trumpet_id, 'leader'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%Take 5%' 
    AND p.name = 'Miles Davis';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, tenor_sax_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%Take 5%' 
    AND p.name = 'John Coltrane';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, piano_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%Take 5%' 
    AND p.name = 'Bill Evans';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, bass_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%Take 5%' 
    AND p.name = 'Paul Chambers';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, drums_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%Take 5%' 
    AND p.name = 'Jimmy Cobb';

    -- Kind of Blue - All Blues
    INSERT INTO recordings (song_id, album_title, recording_date, recording_year, label, is_canonical, notes)
    SELECT id, 'Kind of Blue', '1959-04-22', 1959, 'Columbia Records',
           true,
           '12-bar blues in 6/8 time. Modal approach combining traditional blues with modal jazz.'
    FROM songs WHERE title = 'All Blues';

    -- Add performers for All Blues
    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, trumpet_id, 'leader'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%12-bar blues%' 
    AND p.name = 'Miles Davis';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, alto_sax_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%12-bar blues%' 
    AND p.name = 'Cannonball Adderley';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, tenor_sax_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%12-bar blues%' 
    AND p.name = 'John Coltrane';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, piano_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%12-bar blues%' 
    AND p.name = 'Bill Evans';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, bass_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%12-bar blues%' 
    AND p.name = 'Paul Chambers';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, drums_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Kind of Blue' AND r.notes LIKE '%12-bar blues%' 
    AND p.name = 'Jimmy Cobb';

    -- My Funny Valentine - Chet Baker Sings (1954)
    INSERT INTO recordings (song_id, album_title, recording_year, label, is_canonical, notes)
    SELECT id, 'Chet Baker Sings', 1954, 'Pacific Jazz',
           true,
           'Signature recording that defined Chet Baker''s intimate vocal and trumpet style.'
    FROM songs WHERE title = 'My Funny Valentine';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, vocals_id, 'leader'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Chet Baker Sings'
    AND p.name = 'Chet Baker';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, trumpet_id, 'leader'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Chet Baker Sings'
    AND p.name = 'Chet Baker';

    -- My Funny Valentine - Gerry Mulligan Quartet (1953)
    INSERT INTO recordings (song_id, album_title, recording_year, is_canonical, notes)
    SELECT id, 'Gerry Mulligan Quartet', 1953,
           true,
           'Groundbreaking pianoless quartet recording. Inducted into Library of Congress National Recording Registry in 2015.'
    FROM songs WHERE title = 'My Funny Valentine';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, baritone_sax_id, 'leader'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Gerry Mulligan Quartet' AND r.recording_year = 1953
    AND p.name = 'Gerry Mulligan';

    INSERT INTO recording_performers (recording_id, performer_id, instrument_id, role)
    SELECT r.id, p.id, trumpet_id, 'sideman'
    FROM recordings r, performers p 
    WHERE r.album_title = 'Gerry Mulligan Quartet' AND r.recording_year = 1953
    AND p.name = 'Chet Baker';

END $$;

-- ============================================================================
-- PERFORMER INSTRUMENTS
-- ============================================================================

-- Link performers to their primary instruments
INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'Miles Davis' AND i.name = 'Trumpet';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'John Coltrane' AND i.name = 'Tenor Saxophone';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'Cannonball Adderley' AND i.name = 'Alto Saxophone';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'Bill Evans' AND i.name = 'Piano';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'Paul Chambers' AND i.name = 'Upright Bass';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'Jimmy Cobb' AND i.name = 'Drums';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'Chet Baker' AND i.name = 'Trumpet';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, false
FROM performers p, instruments i
WHERE p.name = 'Chet Baker' AND i.name = 'Vocals';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'Gerry Mulligan' AND i.name = 'Baritone Saxophone';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'Frank Sinatra' AND i.name = 'Vocals';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'Ella Fitzgerald' AND i.name = 'Vocals';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'Charlie Parker' AND i.name = 'Alto Saxophone';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'Dizzy Gillespie' AND i.name = 'Trumpet';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'Wynton Kelly' AND i.name = 'Piano';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'Thelonious Monk' AND i.name = 'Piano';

INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = 'Duke Ellington' AND i.name = 'Piano';

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Count songs loaded
SELECT COUNT(*) as total_songs FROM songs;

-- Count performers loaded
SELECT COUNT(*) as total_performers FROM performers;

-- Count canonical recordings
SELECT COUNT(*) as canonical_recordings FROM recordings WHERE is_canonical = true;

-- View Kind of Blue recordings with performers
SELECT 
    s.title as song,
    r.album_title,
    r.recording_year,
    p.name as performer,
    i.name as instrument,
    rp.role
FROM recordings r
JOIN songs s ON r.song_id = s.id
JOIN recording_performers rp ON r.id = rp.recording_id
JOIN performers p ON rp.performer_id = p.id
LEFT JOIN instruments i ON rp.instrument_id = i.id
WHERE r.album_title = 'Kind of Blue'
ORDER BY r.recording_date, s.title, p.name;

-- ============================================================================
-- NOTES FOR EXTENDING THIS DATABASE
-- ============================================================================

/*
This starter script provides:
- All 250+ jazz standards from Ted Gioia's "The Jazz Standards"
- Detailed information for select iconic standards
- 15 famous jazz performers
- Several canonical recordings from Kind of Blue and other sources
- Proper relationships between songs, recordings, and performers

TO EXTEND THIS DATABASE:
1. Add more performer biographies and external links
2. Add canonical recordings for more songs (search musicbrainz.org, discogs.com)
3. Add YouTube video links for educational content
4. Fill in chord progressions and structure information for more songs
5. Add more albums and complete recording sessions
6. Link performer instruments for all performers
7. Create admin users for your team

RECOMMENDED SOURCES FOR ADDITIONAL DATA:
- Wikipedia for composer and song information
- MusicBrainz (musicbrainz.org) for detailed recording metadata
- Discogs (discogs.com) for album and label information
- AllMusic (allmusic.com) for performer biographies
- Ted Gioia's "The Jazz Standards" book for canonical recordings
- JazzStandards.com for analysis and history
*/
