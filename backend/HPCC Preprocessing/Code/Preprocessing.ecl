IMPORT $;
SpotMusic := $.File_Music.SpotDS;

// Define rock-related genres
RockGenres := ['alt-rock', 'hard-rock', 'heavy-metal', 'psych-rock', 'punk-rock', 'rock', 'rock-n-roll'];

// Layout for unified structure
UnifiedLayout := RECORD
    STRING title;
    STRING375 artist_name;
    STRING genre;
    REAL score;
END;

RockFiltered := SpotMusic(genre IN RockGenres);

// Output the raw data before score processing
OUTPUT(RockFiltered, NAMED('Rock_Related_Songs_Before_Scoring'));

// Filter and score for rock-related genres
SpotScored := PROJECT(RockFiltered,
    TRANSFORM(UnifiedLayout,
        SELF.title := LEFT.track_name;
        SELF.artist_name := LEFT.artist_name;
        SELF.genre := LEFT.genre;
        SELF.score := (0.2 * (REAL)LEFT.tempo) + 
                      (0.2 * (REAL)LEFT.loudness) + 
                      (0.15 * (REAL)(LEFT.danceability)) +
                      (0.15 * (REAL)(LEFT.energy)) +
                      (0.15 * (REAL)(LEFT.instrumentalness))));

// Filter and sort the dataset
FilteredScored := SpotScored(score > 0);
SortedScored := SORT(FilteredScored, -score);

// Top 100 unique songs
Top100 := CHOOSEN(SortedScored, 100);

OUTPUT(Top100, NAMED('Top_100_Rock_Related_Songs_With_Scores'));