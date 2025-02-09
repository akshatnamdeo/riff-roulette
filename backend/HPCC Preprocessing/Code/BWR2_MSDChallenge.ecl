IMPORT $;
MSDMusic := $.File_Music.MSDDS;

//display the first 150 records

OUTPUT(CHOOSEN(MSDMusic, 150), NAMED('Raw_MusicDS'));

//*********************************************************************************
//*********************************************************************************

//                                CATEGORY ONE 

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Reverse Sort by "year" and count your total music dataset and display the first 50

//Result: Total count is 1000000


//Reverse sort by "year"

//display the first 50


//Count and display result

ReverseSorted := SORT(MSDMusic, -year);
OUTPUT(CHOOSEN(ReverseSorted, 50));
OUTPUT(COUNT(MSDMusic)); // Ask


//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Display first 50 songs by of year 2010 and then count the total 

//Result should have 9397 songs for 2010

//Filter for 2010 and display the first 50


//Count total songs released in 2010:

Filtered2010 := MSDMusic(year = 2010);
OUTPUT(CHOOSEN(Filtered2010, 50));
OUTPUT(COUNT(Filtered2010));

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Count how many songs was produced by "Prince" in 1982

//Result should have 4 counts

//Filter ds for "Prince" AND 1982

//Count and print total 

OUTPUT(COUNT(MSDMusic(artist_name = 'Prince' AND year = 1982)));

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Who sang "Into Temptation"?

// Result should have 3 records

//Filter for "Into Temptation"


//Display result 

OUTPUT(MSDMusic(title = 'Into Temptation'));

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Sort songs by Artist and song title, output the first 100

//Result: The first 10 records have no artist name, followed by "- PlusMinus"                                     

//Sort dataset by Artist, and Title


//Output the first 100

OUTPUT(CHOOSEN(SORT(MSDMusic, artist_name, title), 100));

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//What is the hottest song by year in the Million Song Dataset?
//Sort Result by Year (filter iut zero Year values)

//Result is 

//Get the datasets maximum hotness value



//Filter dataset for the maxHot value


//Display the result

// HottestByYear := SORT(MSDMusic(year != 0), year);
// MaxHotness := MAX(HottestByYear, song_hotness);
// OUTPUT(HottestByYear(song_hotness = MaxHotness)); // Ask

SortedSongs := SORT(MSDMusic(year != 0 AND song_hotness > 0), year, -song_hotness);
HottestByYear := DEDUP(SortedSongs, year);
OUTPUT(SORT(HottestByYear, year)); // Ask

//*********************************************************************************
//*********************************************************************************

//                                CATEGORY TWO

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Display all songs produced by the artist "Coldplay" AND has a 
//"Song Hotness" greater or equal to .75 ( >= .75 ) , SORT it by title.
//Count the total result

//Result has 47 records

//Get songs by defined conditions

FilteredSongsColdplay := MSDMusic(artist_name = 'Coldplay' AND song_hotness >= .75);

//Sort the result

SortedSongsColdplay := SORT(FilteredSongsColdplay, title);

//Output the result

OUTPUT(SortedSongsColdplay);

//Count and output result

OUTPUT(COUNT(SortedSongsColdplay));


//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Count all songs where "Duration" is between 200 AND 250 (inclusive) 
//AND "song_hotness" is not equal to 0 
//AND familarity > .9

//Result is 762 songs  

//Hint: (SongDuration BETWEEN 200 AND 250)

//Filter for required conditions

//Count result
DurationFilter := MSDMusic(duration BETWEEN 200 AND 250 AND song_hotness <> 0 AND familiarity > .9);
OUTPUT(COUNT(DurationFilter), NAMED('DurationFilter_Count'));

//Display result
OUTPUT(CHOOSEN(DurationFilter, 50), NAMED('DurationFilter_Songs'));


//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Create a new dataset which only has  "Title", "Artist_Name", "Release_Name" and "Year"
//Display the first 50

//Result should only have 4 columns. 

//Hint: Create your new RECORD layout and use TRANSFORM for new fields. 
//Use PROJECT, to loop through your music dataset

NewDatasetLayout := RECORD STRING title; STRING artist_name; STRING release_name; UNSIGNED4 year; END;

//Standalone Transform 
//PROJECT
NewDataset := PROJECT(MSDMusic, TRANSFORM(NewDatasetLayout, SELF.title := LEFT.title; SELF.artist_name := LEFT.artist_name; SELF.release_name := LEFT.release_name; SELF.year := LEFT.year));

// Display result  
OUTPUT(CHOOSEN(NewDataset, 50), NAMED('NewDataset'));

//*********************************************************************************
//*********************************************************************************

//Challenge: 
//1- What’s the correlation between "song_hotness" AND "artist_hotness"
//2- What’s the correlation between "barsstartdev" AND "beatsstartdev"

//Result for hotness = 0.4706972681953097, StartDev = 0.8896342348554744
HotnessValidation := MSDMusic(song_hotness > 0 AND artist_hotness > 0);
HotnessCorrelation := CORRELATION(HotnessValidation, song_hotness, artist_hotness);
OUTPUT(HotnessCorrelation);
StartDevValidation := MSDMusic(barsstartdev > 0 AND beatsstartdev > 0);
StartDevCorrelation := CORRELATION(StartDevValidation, BarsStartDev, BeatsStartDev);
OUTPUT(StartDevCorrelation);


//*********************************************************************************
//*********************************************************************************

//                                CATEGORY THREE

//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Create a new dataset which only has following conditions
//   *  Column named "Song" that has "Title" values 
//   *  Column named "Artist" that has "artist_name" values 
//   *  New BOOLEAN Column called isPopular, and it's TRUE is IF "song_hotness" is greater than .80
//   *  New BOOLEAN Column called "IsTooLoud" which is TRUE IF "Loudness" > 0
//Display the first 50
NewDataset2 := RECORD
    STRING Song;
    STRING Artist;
    BOOLEAN isPopular;
    BOOLEAN IsTooLoud;
END;
OUTPUT(CHOOSEN(PROJECT(MSDMusic, TRANSFORM(NewDataset2, SELF.Song := LEFT.title; SELF.Artist := LEFT.artist_name; SELF.isPopular := LEFT.song_hotness > .80; SELF.IsTooLoud := LEFT.loudness > 0)), 50), NAMED('NewDataset2'));

//Result should have 4 columns named "Song", "Artist", "isPopular", and "IsTooLoud"


//Hint: Create your new layout and use TRANSFORM for new fields. 
//      Use PROJECT, to loop through your music dataset

//Create the RECORD layout


//Build your TRANSFORM

//Creating the PROJECT


//Display the result



//*********************************************************************************
//*********************************************************************************
//Challenge: 
//Display number of songs per "Year" and count your total 

//Result has 2 col, Year and TotalSongs, count is 89

//Hint: All you need is a cross-tab TABLE 

//Display the  result      

//Count and display total number of years counted

YearCount_Songs := TABLE(MSDMusic, {year, UNSIGNED TotalSongs := COUNT(GROUP)}, year);
OUTPUT(YearCount_Songs, NAMED('YearCount_Songs'));
OUTPUT(COUNT(YearCount_Songs), NAMED('YearCount'));


//*********************************************************************************
//*********************************************************************************
// What Artist had the overall hottest songs between 2006-2007?
// Calculate average "song_hotness" per "Artist_name" for "Year" 2006 and 2007

// Hint: All you need is a TABLE, and see the TOPN function for your OUTPUT 

// Output the top ten results showing two columns, Artist_Name, and HotRate.

// Filter for year

// Create a Cross-Tab TABLE:

// Display the top ten results with top "HotRate"

OverallArtist := MSDMusic(year = 2006 OR year = 2007);
ArtistSongHotness := TABLE(OverallArtist, {artist_name, REAL HotRate := AVE(GROUP, song_hotness)}, artist_name);
OUTPUT(TOPN(ArtistSongHotness, 10, -HotRate), NAMED('ArtistSongHotness'));

