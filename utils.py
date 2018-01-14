import timehandler as th
import sqlite3
import config
import codecs
import sys
import feedparser
from datetime import datetime ,timedelta
from tvMediaApi_dev import TvMedia

api = TvMedia(config.APIKEY,config.BASE_URL)

reload(sys)
sys.setdefaultencoding('utf-8')


conn = sqlite3.connect(config.DATABASE)
conn.row_factory = sqlite3.Row
# conn.text_factory = str
cursor = conn.cursor()
 
START = config.DEFAULT_START
STOP = config.DEFAULT_STOP
DATETODAY = th.date_today()

def get_events():

	''' Connects to rss feed of UC calendar. Parses event and dates and inserts into db. Note rss feed for events which 
	span multiple days simply gives beginning and end date. If this is the case conditional inserts missing dates'''
	#create rss parser object using URL below
	try:
		rss = feedparser.parse('http://www.unitedcenter.com/rss/events.aspx')
		#deletes all events from table each time function runs
		cursor.execute('''DELETE FROM ucEventCalendar''')
		
		for i in rss['entries']:
			event = i['title']
			date = i['event_date']
			# Conditional inserts new actual dates for events spanning datemin "-" date max
			if "-" in date:
				dates = date.split('-')
				# removes named day "CST" and trailing whitespace
				dates = [ i.split(',')[1].strip()[:-4] for i in dates]
				#convert string dates to datetime objects
				dateMax = datetime.strptime(dates[1],"%d %b %Y %H:%M:%S")
				dateMin = datetime.strptime(dates[0],"%d %b %Y %H:%M:%S")
				#derive duration of event days
				total_event_days = dateMax - dateMin
				#loop through events and add missing dates
				for i in range(0,abs(total_event_days.days)+1):
					date = dateMin + timedelta(days=i)
					dbinsert(date,event)
				
			else:
				# removes named day "CST" and trailing whitespace
				date = date.split(',')[1].strip()[:-4]
				#convert string dates to datetime objects
				date = datetime.strptime(date,"%d %b %Y %H:%M:%S")
				dbinsert(date,event)
				print date,event

	except Exception as e:

		print "Error getting new events from UC cal", e.args



def dbinsert(date,event):

		_date = date.strftime('%Y-%m-%d')
		_time = date.strftime('%H:%M:%S')

		cursor.execute(''' INSERT INTO ucEventCalendar (date,time,event)
								VALUES (?,?,?)''',(_date,_time,event))
		conn.commit()

def combiner(listings):

	seen = []
	newRows = []

	for i in listings:

		# print i['channelName'],i['uctvNo'],i['HD'],i['SD']

		if i['listingID'] not in seen:
			i['SD'] = i['uctvNo'] if i['HD'] == None else ''
			seen.append(i['listingID']);	
		else:
			#print i['uctvNo'],i['HD'],i['channelName']
			row = [x for x in listings if x['listingID']==i['listingID']]
			uctvNo = row[0]['uctvNo'] if row[0]['HD'] == 1 else row[1]['uctvNo']		
			SD = row[1]['uctvNo'] if row[1]['HD'] == None else row[0]['uctvNo']
			HD = row[0]['HD']
			listingID = row[0]['listingID']
			event = row[0]['event']
			sport = row[0]['sport']
			channelName = row[0]['channelName']
			startTime = row[0]['startTime']
			newRow = {'sport':sport,'event':event,'listingID':listingID,'HD':HD,'SD':SD,'channelName':channelName,'uctvNo':uctvNo,'startTime':startTime}
			newRows.append(newRow)

	newRowIds = [x['listingID'] for x in newRows]
	newlistings = [x for x in listings if x['listingID'] not in newRowIds]

	return newRows + newlistings	

def check_for_event(date,db):
	
	query = db.execute('''SELECT * FROM ucEventCalendar WHERE date = ?''',(date,))
	result = query.fetchone()
	# result = ('nothing','nothingh','7pm','testevent')

	if result:
		event_start = result[2]
		event = result[3]
		return event,event_start
	else:
		
		return ("No Event")

def get_lineup_listings(start,stop,date,lineups,cursor):

	print "Getting Lineup Listings"
	#nuild list of start end times for api request
	times = th.get_utc_start_end_times()
	# get list of station ids in channel plan
	query = cursor.execute('''SELECT DISTINCT stationID from uctvLineups WHERE uctvNo NOT NULL''')
	stationIDs = [i[0] for i in query.fetchall()]


	

	cursor.execute('''DELETE FROM liveSports''')
	cursor.execute('''DELETE FROM crestronLiveSports''')
	
	cursor.connection.commit()
	
	try:
		for time in times:
			listings = [api.lineup_listings(i,start=time[0],end=time[1],sportEventsOnly=1,liveOnly=1) for i in lineups]
			
			for lineup in listings:
				
				for i in lineup:
					if i['stationID'] in stationIDs :

						if i['live'] and i['team1']:
							event = i['team1'] + ' at '+ i['team2']
						
						elif i['live'] and i['event']:
							event = i['event']

						elif i['live'] and ['description']:
							event = i['description']

						elif i['live'] and i['showName']:
							event = i['location'] 

						

						startTime = th.format_time(th.convert_utc_to_local(i['listDateTime']))
						date = startTime[0]
						startTime = startTime[1]
						duration = i['duration']
						sport = i['showName']
						#strip commas from events or else it screws up the way node red parses column data
						print event
						event = event.replace(',',' ')
						print event

						stationID = i['stationID']
						stopTime = th.addTime(startTime,duration)
						listingID = i['listingID']
						#print i['listDateTime'],startTime,sport,stationID,listingID

						
						cursor.execute('''INSERT INTO liveSports (stationID,date,startTime,duration,stopTime,sport,event,listingID)
										VALUES (?,?,?,?,?,?,?,?)''',(stationID,date,startTime,duration,stopTime,sport,event,listingID))

	except Exception as e:
		print "Get Lineups Listings failed with error %s" % e

						
	cursor.execute('''UPDATE liveSports
					SET 
					uctvNo = (SELECT uctvNo FROM uctvLineups WHERE uctvLineups.stationID = liveSports.stationID AND uctvLineups.uctvNo NOT NULL),
					channelName = (SELECT channelName FROM uctvLineups WHERE uctvLineups.stationID = liveSports.stationID)	''')
	# cursor.connection.commit()

	cursor.execute('''DELETE FROM liveSports
					WHERE id
					IN (SELECT id FROM liveSports
					GROUP BY stationID,channelName,date,startTime
					HAVING COUNT(*) >1) ''')
	#clean up live sport
	print " insert into crestron live sports"						
	cursor.execute('''INSERT INTO crestronLiveSports (channelName,uctvNo,sport,date,startTime,stopTime,duration,event)
			SELECT DISTINCT uctvLineups.channelName,
					uctvLineups.uctvNo,
					liveSports.sport,
					liveSports.date,
					liveSports.startTime,
					liveSports.stopTime,
					liveSports.duration,
					liveSports.event
			FROM livesports
			INNER JOIN uctvLineups
			ON uctvLineups.stationID = liveSports.stationID
			WHERE uctvlineups.crestron = 1 ''')
								
	cursor.connection.commit()

def getChannels(db):

	query = db.execute('''SELECT id,channelNumber,channelName,uctvNo,providerName,HD
						   FROM uctvLineups 
						   WHERE uctvNo NOT NULL
						   ORDER BY uctvNo''')

	channels = [dict(row) for row in query.fetchall()]
	
	return channels

def getCrestronLiveSports(db):

	print "getting crestron live sport {}".format(th.date_today())

	query = db.execute('''SELECT * FROM crestronLiveSports 
						  WHERE date = ?
						 ORDER BY startTime''',(th.date_today(),))

	liveSports = [dict(row) for row in query.fetchall()]

	return liveSports

def get_live_sports(date,start,stop,cursor):

		query = cursor.execute('''  SELECT DISTINCT uctvLineups.uctvNo,uctvLineups.channelName,listingID,HD,sport,event,startTime
							FROM liveSports 
							INNER JOIN uctvLineups
							ON livesports.stationID = uctvLineups.stationID
							WHERE date = ? 
							AND  startTime BETWEEN ? AND ? AND uctvLineups.uctvNo NOT NULL''',(date,start,stop))

		liveSports = [dict(row) for row in query.fetchall()]
	
		sportslist = th.sort_by_time(liveSports)

		return sportslist

def make_infocaster_file(startTime,stopTime,date,cursor):
	print "Making INfocaster file"
	start = startTime
	stop = stopTime

	# query = cursor.execute('''  SELECT DISTINCT uctvLineups.uctvNo,uctvLineups.channelName,listingID,HD,sport,event,startTime
	# 						FROM liveSports 
	# 						INNER JOIN uctvLineups
	# 						ON livesports.stationID = uctvLineups.stationID
	# 						WHERE date = ? 
	# 						AND  startTime BETWEEN ? AND ? AND uctvLineups.uctvNo NOT NULL
	# 						''',(date,start,stop))

	query = cursor.execute('''SELECT DISTINCT uctvNo,channelName,sport,event,startTime
							FROM liveSports
							WHERE date = ?
							AND startTime BETWEEN ? and ? ''',(date,start,stop))

	listings = [dict(row) for row in query.fetchall()]
	
	sortedListings = sorted(listings,key=lambda d:(d['sport'],d['startTime']))
	csport = None
	
	with open(config.INFOCASTER_TEXT_FILE,'w') as f:

		for i in sortedListings:
		
			startTime = th.convert_to_am_pm(i['startTime'])

			# if i['SD'] == i['uctvNo']:
			# 	hd = ''
			# 	sd = i['SD']
			# else:
			# 	hd = i['uctvNo']
			# 	sd = i['SD']
			
			#handle events that are too long to fit in line
			event = i['event'] if not len(i['event']) > 42 else i['event'][:42] + '..'
			#remove comma from event to stop ffing up csv file
			event = event.replace(',',' ')
		
		
			if csport == i['sport']:
				row = ",%s,%s,%s,%s,%s\n" % (startTime,event,i['channelName'],i['uctvNo'],'')
				f.write(row)

			else:
				row = "%s,,,,,\n" % i['sport']
				f.write(row)
				row = ",%s,%s,%s,%s,%s\n" % (startTime,event,i['channelName'],i['uctvNo'],'')
				f.write(row)
				csport = i['sport']
# make_infocaster_file(START,STOP,DATETODAY,cursor)

def make_crestron_live_sports_file(date,cursor):

	query = cursor.execute('''SELECT * FROM crestronLiveSports WHERE date = ?''',(date,))
	
	liveSports = [dict(row) for row in query.fetchall()]

	
	
	with open(config.CRESTRON_LIVE_FILE,'w') as file:

		for i in liveSports:
			event = i['event']
			event  = '<FONT size=""30"" face=""Crestron Sans Pro"" color=""#ffffff"">'+event+'</FONT>'
			# Note conversion of duration from int to string. This was to fix a node red bug that was preventing crestron parsing live.txt file
			line = [i['sport'],event,i['date'],i['startTime'],str(i['duration']),i['stopTime'],i['channelName'],i['uctvNo'],'\n']
			newline = ','.join(i for i in line)
		
			file.write(newline)










