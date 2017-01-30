import sqlite3
import config

conn = sqlite3.connect('uctvdb')

conn.row_factory = sqlite3.Row
c = conn.cursor()

remove1 = ["NBA League Pass","NHL Centre Ice","NHL League Wide","NHL Centre Ice Extra"]
remove2 = [
	3.3,
	3.3,
	4.1,
	4.2,
	90.1,
	90.2,
	91.1,
	91.2,
	92.1,
	92.2,
	93.1
]

removeThese = [str(i) for i in remove2]

addBack =  ['NHL Centre Ice HD 1']


query = c.execute('''SELECT id,channelNumber,callsign,channelName,uctvNo,stationID,lineupID 
							   FROM uctvLineups 
							   WHERE uctvNo != ?
							   ORDER BY channelName''',('None',))


result = [dict(row) for row in query.fetchall()]


with open('testGuideMaker.txt','w') as file:

	for i in result:
		#strip whitespace
		channelName = i['channelName'].strip()
	
		#ignore channels in remove 1/2
		if channelName not in addBack and  any(channel in channelName for channel in remove1)  or i['uctvNo'] in removeThese:
			continue
		print type(i['uctvNo'])
		#handle ampersands for html which todate is only an issue with A&E 
		if "&" in channelName:
			channelName = channelName.replace('&','&amp;')
		
		#strings to delete from guide because not needed
		deletes =['HD','Network','Channel','Guide','League','Wide']

		for string in deletes:
			if string  in channelName:
				channelName = channelName.replace(string,'')
			
	
		#build special crestron html
		channel = r'<FONT size=""30"" face=""Crestron Sans Pro"" color=""#ffffff"">'+channelName+'</FONT>'
		uctvNo = str(i['uctvNo'])
		emptyfield = "URL"

		line = channel +','+uctvNo+','+emptyfield+'\n'
		print line
		file.write(line)


		