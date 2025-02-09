#OPTION('obfuscateOutput', TRUE);
IMPORT $;
MozMusic := $.File_Music.MozDS;

//display the first 150 records
OUTPUT(CHOOSEN(MozMusic, 150), NAMED('Moz_MusicDS'));

//*********************************************************************************
//*********************************************************************************

//                                CATEGORY ONE 

//*********************************************************************************
//*********************************************************************************

//Challenge: 
//Count all the records in the dataset:

COUNT(MozMusic);

//Result: Total count is 136510

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Sort by "name",  and display (OUTPUT) the first 50(Hint: use CHOOSEN):
//You should see a lot of songs by NSync 

OUTPUT(CHOOSEN(SORT(MozMusic, name), 50));

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Count total songs in the "Rock" genre and display number:

// MOZMUSIC(genre='Country');
//Result should have 12821 Rock songs

//Display your Rock songs (OUTPUT):
RockGenreSongs := MozMusic(genre = 'Rock');
OUTPUT(COUNT(RockGenreSongs));
OUTPUT(CHOOSEN(RockGenreSongs, 50));

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Count how many songs was released by Depeche Mode between 1980 and 1989
//Filter ds for "Depeche_Mode" AND releasedate BETWEEN 1980 and 1989
// Count and display total
//Result should have 127 songs 

DepecheModeRecords := MozMusic(name = 'Depeche_Mode' AND releasedate >= '1980' AND releasedate <= '1989');
OUTPUT(COUNT(DepecheModeRecords));

//Bonus points: filter out duplicate tracks (Hint: look at DEDUP):
DedupDepecheModeRecords := DEDUP(SORT(DepecheModeRecords, tracktitle), tracktitle);
OUTPUT(COUNT(DedupDepecheModeRecords));

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Who sang the song "My Way"?
//Filter for "My Way" tracktitle
// Result should have 136 records 
//Display count and result 

MyWay := MozMusic(tracktitle = 'My Way');
OUTPUT(COUNT(MyWay));
OUTPUT(MyWay);

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//What song(s) in the Music Moz Dataset has the longest track title in CD format?
//Get the longest description (tracktitle) field length in CD "formats"
//Filter dataset for tracktitle with the longest value
//Display the result
//Longest track title is by the "The Brand New Heavies"               

TracksWithLength := PROJECT(MozMusic(formats = 'CD'),
    TRANSFORM(RECORD
        STRING tracktitle;
        STRING artist;
        UNSIGNED titleLen;
    END,
        SELF.tracktitle := LEFT.tracktitle;
        SELF.artist := LEFT.name;
        SELF.titleLen := LENGTH(TRIM(LEFT.tracktitle));
    ));

LongestTracks := SORT(TracksWithLength, -titleLen);
OUTPUT(CHOOSEN(LongestTracks, 1));



//*********************************************************************************
//*********************************************************************************

//                                CATEGORY TWO

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Display all songs produced by "U2" , SORT it by title.
//Filter track by artist
//Sort the result by tracktitle
//Output the result
//Count result 
//Result has 190 records

U2Songs := SORT(MozMusic(name = 'U2'), tracktitle);
OUTPUT(U2Songs);
OUTPUT(COUNT(U2Songs));

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Count all songs where guest musicians appeared 
//Hint: Think of the filter as "not blank" 
//Filter for "guestmusicians"
//Display Count result
//Result should be 44588 songs  

GuestMusicians := MozMusic(guestmusicians <> '');
OUTPUT(COUNT(GuestMusicians));

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Create a new recordset which only has "Track", "Release", "Artist", and "Year"
// Get the "track" value from the MusicMoz TrackTitle field
// Get the "release" value from the MusicMoz Title field
// Get the "artist" value from the MusicMoz Name field
// Get the "year" value from the MusicMoz ReleaseDate field
//Result should only have 4 fields. 
//Hint: First create your new RECORD layout  

NewLayout := RECORD
    STRING track;
    STRING release;
    STRING artist;
    STRING4 year;
END;

//Next: Standalone Transform - use TRANSFORM for new fields.
NewLayout TransformMoz(MozMusic L) := TRANSFORM
    SELF.track := L.tracktitle;
    SELF.release := L.title;
    SELF.artist := L.name;
    SELF.year := L.releasedate[1..4];
END;

//Use PROJECT, to loop through your music dataset
SimplifiedDS := PROJECT(MozMusic, TransformMoz(LEFT));

// Display result  
OUTPUT(CHOOSEN(SimplifiedDS, 50));

//*********************************************************************************
//*********************************************************************************

//                                CATEGORY THREE

//*********************************************************************************
//*********************************************************************************

//Challenge: 
//Display number of songs per "Genre", display genre name and count for each 
//Hint: All you need is a 2 field TABLE using cross-tab
//Display the TABLE result      
//Count and display total records in TABLE
//Result has 2 fields, Genre and TotalSongs, count is 1000

GenreCounts := TABLE(MozMusic, {genre, UNSIGNED4 TotalSongs := COUNT(GROUP)}, genre);
OUTPUT(GenreCounts);
OUTPUT(COUNT(GenreCounts));

//*********************************************************************************
//*********************************************************************************
//What Artist had the most releases between 2001-2010 (releasedate)?
//Hint: All you need is a cross-tab TABLE 
//Output Name, and Title Count(TitleCnt)
//Filter for year (releasedate)
//Cross-tab TABLE
//Display the result      

Releases := MozMusic(releasedate >= '2001' AND releasedate <= '2010');
ReleasesByArtist := TABLE(Releases, {name, UNSIGNED4 TitleCnt := COUNT(GROUP)}, name);
MostReleases := SORT(ReleasesByArtist, -TitleCnt);
OUTPUT(CHOOSEN(MostReleases, 1));