from flask import Flask, request, session, g, redirect, url_for, render_template, flash,jsonify
import config
import sqlite3
import timehandler as th
# import sevenDaySchedule as sds
# import make_infocastertxt_sports_for_today as misft
import pdfkit
import utils
import json


from tvMediaApi_dev import TvMedia

app = Flask(__name__)
app.config.from_object(config)

START = config.DEFAULT_START
STOP = config.DEFAULT_STOP
DATETODAY = th.date_today()

api = TvMedia(config.APIKEY,config.BASE_URL)

def connect_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    return cursor

@app.before_request
def before_request():
	g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
	db = getattr(g, 'db', None)
	
	if db is not None:
		db.close()

#Error******************************************************************************************************
# @app.errorhandler(404)
# def page_not_found(error):
#     return redirect(url_for('index'))

# Index  ******************************************************************************************************
@app.route('/')
def index():
	event = utils.check_for_event(th.date_today(),g.db);
	
	return render_template('index.html',event=event)

# Channel Guide **********************************************************************************************
@app.route('/channelGuide',methods=['GET','POST'])
def channelGuide():

	if request.method == 'GET':
	
		channels = utils.getChannels(g.db)

	elif request.method == 'POST':
		
		columnName = request.form['columnName']
		rowid = request.form['id']
		value = request.form[columnName]

		utils.updateUctvLineups(columnName,rowid,value)

		return jsonify(error=0,message="Database changes saved")
      
	return render_template('Guides/channelGuide.html',channels=channels)

# Live Sports Schedule **********************************************************************************************
@app.route('/liveSports',methods=['GET','POST'])
def liveSports():

	if request.method == 'GET':
		print 'GETTING SPORTS ' + DATETODAY,START,STOP
		sportslist = utils.get_live_sports(DATETODAY,START,STOP,g.db)
	
		return render_template('LiveSports/liveSports.html',sportslist=sportslist)

	#submit new date time range for query
	elif request.method == 'POST':
		
		date = th.convert_date_string(request.form['date'])
		start = th.convert_time_string(request.form['start'])
		stop = th.convert_time_string(request.form['stop']) 
		# sportslist = utils.getLiveSports(DATETODAY,START,STOP,g.db)
		sportslist = utils.get_live_sports(date,start,stop,g.db)

		
		return render_template('LiveSports/liveSportsTable.html',sportslist=sportslist,request=request)
@app.route('/editLiveSports',methods=['GET','POST'])
def edit():

	sportslist = utils.get_live_sports(DATETODAY,START,STOP,g.db)
	
	return render_template('LiveSports/liveSportsEdit.html',sportslist=sportslist)

	
@app.route('/saveLiveSportsEdit',methods=['POST'])
def save():
	
		try:
			for id,row in request.form.iterlists():
				
				if id != 'delete':
				
					row[1] = th.convert_time_string(row[1])
					#adds id to end of row list
					row.append(id)
					print row
					
					g.db.execute('''UPDATE liveSports SET event=?,startTime=?
					WHERE listingID = ?''',row)

			deletions = [(int(i),) for i in request.form.getlist('delete')]
			g.db.executemany('''DELETE from liveSports where listingID = ?''',deletions)
			g.db.connection.commit()
		
			sportslist = utils.get_live_sports(DATETODAY,START,STOP,g.db)
			response = render_template('LiveSports/liveSportsTable.html',sportslist=sportslist)
			return jsonify(html=response,error=0,message="Live Sports Updated");

		except sqlite3.Error,e:

			return jsonify(error=1,message="Error!! %s" % e.args[0]) 

@app.route('/add',methods=['GET','POST'])
def add():
	print "adding new event"
	try:
		r = request.form
		import random
		listingID = random.randint(1,100)
		date = th.date_today()
		time = th.convert_time_string(r['time'])
		row = [date,time,r['event'],r['sport'],r['stationID'],listingID]
		g.db.execute('''INSERT INTO liveSports (date,startTime,event,sport,stationID,listingID)
						VALUES (?,?,?,?,?,?)''',row)

		g.db.connection.commit()

		sportslist = utils.get_live_sports(DATETODAY,START,STOP,g.db)
		response = render_template('LiveSports/liveSportsTable.html',sportslist=sportslist)
		return jsonify(html=response,error=0,message="Event Added");

	except Exception as e:

		print "Error" + e.args[0]
		# return jsonify(error=1,message="Publish Infocast failed!!!: %s" % e.args[0])
		return e.args[0]
# Email
@app.route('/email',methods=['GET','POST'])
def email():

	if request.method == 'GET':

		sportslist = get_live_sports(DATETODAY,START,STOP)
	else:

		date = th.convert_date_string(request.form['date'])
		start = th.convert_time_string(request.form['start'])
		stop = th.convert_time_string(request.form['stop']) 

		sportslist = utils.get_live_sports(date,start,stop,g.db)

	return render_template('LiveSports/email.html',sportslist=sportslist,date=request.form['date'])
#PDF
@app.route('/pdf',methods=['POST'])
def pdf():
	pdfconfig = pdfkit.configuration(wkhtmltopdf=config.EXE_WKHTMLTOPDF)

	pdf_options = {
	'page-width':'1.5in',
    'page-size': 'Letter',
    'margin-top': '0.75in',
    'margin-right': '0.75in',
    'margin-bottom': '0.75in',
    'margin-left': '1.0in',
    'encoding': "UTF-8",
    'no-outline': None
	}
               
	pdf_filename = 'UCTV Sports Schedule '+ request.json['date'].replace('/','-') +'.pdf'
	
	out_pdf = config.DIR_SPORTS_PDF + '\\' + pdf_filename

	css ='''<style> table,th,td{
    border:1px solid black;
    border-collapse: collapse;
    font-family: Arial;
    font-size: 11pt;}

    table{width:800px;}

    input{border:0px;}
	
    h3{border:0px;font-family:Arial;font-size:20pt;}
    .pdf_no_show{display:none;}
  
    tr.pdf input[type="text"],tr.pdf td{background-color:FCAE1C;} 

    th{background-color:#7AABEB;}
    td{padding:2px;}</style>\n'''

	with open("pdf.html",'wb') as f:
		f.write(css)
		f.write(request.json['page'].encode('utf-8'))

	pdfkit.from_file('pdf.html', out_pdf,configuration=pdfconfig,options=pdf_options)

	return "Successfully created %s" % out_pdf
# Reload database from API **********************************************************************************************
@app.route('/reloadSports')
def reloadSports():

	print "reload sports"

	try: 
		print "trying"
		utils.get_lineup_listings(START,STOP,DATETODAY,config.LINEUPS,g.db)

		sportslist = utils.get_live_sports(DATETODAY,START,STOP,g.db)
	
		print sportslist
		return render_template('LiveSports/liveSportsTable.html',sportslist=sportslist)
	except Exception as e:
		print e.args
		return jsonify(error=1,message="Reload failed!!! %s" % e.args[0])


# Crestron Live Sports **********************************************************************************************
@app.route('/crestronLiveSports')
def crestronLiveSports():

	# liveSports = utils.getLiveSportsWithId(g.db)
	liveSports = utils.getCrestronLiveSports(g.db)
	event = utils.check_for_event(th.date_today(),g.db);

	return render_template('LiveSports/crestronLiveSports.html',liveSports=liveSports,event=event)	
@app.route('/editCrestronLiveSports',methods=['GET','POST'])
def editCrestronLiveSports():

	if request.method == 'GET':

		liveSports = utils.getCrestronLiveSports(g.db)

		return render_template('LiveSports/crestronLiveSportsEdit.html',liveSports=liveSports,event='test')

	try:
		#hack to get delete thing working
		for id,row in request.form.iterlists():
			if id == 'delete':
				continue
		
	 		row.append(id)
	 	
	 		g.db.execute('''UPDATE crestronLiveSports 
	 				SET sport=?,
	 					event=?,
	 					date=?,
	 					startTime=?,
	 					duration=?,
	 					stopTime=?,
	 					channelName=?,
	 					uctvNo=?
	 					WHERE id = ?''',row)


	 	deletions = [(int(i),) for i in request.form.getlist('delete')]
	 	print request.form.getlist('delete')
		g.db.executemany('''DELETE from crestronliveSports where id = ?''',deletions)
		g.db.connection.commit()
		print 'commited changes'
	except Exception as e:
		
		return jsonify(error=1,message="Error!! %s" % e.args[0]) 
	utils.make_crestron_live_sports_file(th.date_today(),g.db)
	
	liveSports = utils.getCrestronLiveSports(g.db)

	return render_template('LiveSports/crestronLiveSportsTable.html',liveSports=liveSports)		
@app.route('/crestronLiveSportsReload')
def reload():
	print g.db
	utils.update_crestron_live_sports_db(g.db)

	liveSports = utils.getCrestronLiveSports(g.db)

	return render_template('LiveSports/crestronLiveSportsEdit.html',liveSports=liveSports,event='test')


# Channel Lineup**********************************************************************************************
@app.route('/lineups',methods=['GET','POST'])
def channelLineup():

	if request.method == 'GET':
		query= g.db.execute('''SELECT * from uctvLineups ''')
		channelLineups = [dict(row) for row in query.fetchall()]
		
		return render_template('Lineups/channelLineups.html',channelLineups=channelLineups)


	for i in request.form.getlist('edits[]'):
		row = json.loads(i)
		col = row['col']
		val = row['value']
		id = row['id']
		print id,col,
		g.db.execute('UPDATE uctvlineups SET ' + col + ' = ? WHERE id = ?',(val,id))
	g.db.connection.commit()
		


	query= g.db.execute('''select * from uctvLineups ''')
	channelLineups = [dict(row) for row in query.fetchall()]
	return render_template('Lineups/channelLineups.html',channelLineups=channelLineups)
@app.route('/addStation',methods=['POST'])
def addStation():

		if request.method == 'POST':

			form = request.form

		
			channelName = form['channelName']
			uctvNo = form['uctvNo']
			lineupID = 1994

			HD = 1 if 'HD' in form else 0
			crestron = 1 if 'crestron' in form else 0
			# print channelName,uctvNo,lineupID,crestron,HD

			g.db.execute('''INSERT INTO uctvLineups (channelName,uctvNo,lineupID,HD,crestron)
						VALUES (?,?,?,?,?)''',(channelName,uctvNo,lineupID,HD,crestron))

			g.db.connection.commit()
		

			return 'success'


			
		return 'fail'

@app.route('/findLineup',methods=['POST'])
def addLineup():

		zipcode = request.form['zipcode']
		
		lineups = api.lineups(zipcode)
		
		return render_template('Lineups/availableLineups.html',lineups=lineups)

# Documentation **********************************************************************************************
@app.route('/docs')
def docs():

	return render_template('Docs/docs.html')

# Directv FaultLog **********************************************************************************************

# @app.route('/directvFaultLog')
# def directvFaultLog():
# 	return render_template('directvFaultLog/directvFaultLog.html')
#Publishes infocaster text file **********************************************************************************************
@app.route('/infocast',methods=['POST'])
def publish_infocast():

	try:
		formDate = th.convert_date_string(request.form['date'])
		formStart = th.convert_time_string(request.form['start'])
		formStop = th.convert_time_string(request.form['stop']) 
		print formDate,formStart,formStop
		utils.make_infocaster_file(formStart,formStop,formDate,g.db)

		return jsonify(error=0,message="Infocaster Text File Updated at %s" % (config.INFOCASTER_TEXT_FILE))

	except Exception as e:

		return jsonify(error=1,message="Publish Infocast failed!!!: %s" % e.args[0])
	
@app.route('/sandbox')
def sandbox():

	return render_template('sandbox/sandbox.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=config.PORT)




