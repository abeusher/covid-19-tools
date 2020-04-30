#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Purpose: Core class structures for JHU CSSE's Time Series Data Files
#
import numpy as np
import shapefile
from datetime import datetime
from datetime import timedelta
import pickle

class Error(Exception):
	"""Base class for exceptions in this module."""
	pass
	
class UsageError(Error):
	"""Exception raised for errors in using the framework.
	
	Attributes:
		expression -- input expression in which the error occurred
		message -- explanation of the error
	"""
	
	def __init__(self, expression, message = ''):
		self.expression = expression
		self.message = message

# basic lat/lon attributes
class Place:
	
	def __init__(self, lat, lon):
		self.a = {} # attributes
		self.a['lat'] = round(lat, 6)
		self.a['lon'] = round(lon, 6)
	
	def lat(self):
		return self.a['lat']
		
	def lon(self):
		return self.a['lat']
	
	def __str__(self):
		return self.a['lat'] + ',' + self.a['lon']

# workhorse used for ADM1, ADM2, ADM3, ...
class Area(Place):
	
	def __init__(self, parent, name, lat=0.0, lon=0.0):
		super().__init__(lat, lon)
		self.__parent = parent # parent obj
		self.a['name'] = name
		self.a['level'] = -1 # -1 is undefined and unset
		self.a['key'] = name # key is rebuilt as hierarchy develops
		self.a['adm1'] = 'N/A'
		self.a['adm2'] = 'N/A'
		self.a['adm3'] = 'N/A'
		self.a['fips'] = 'N/A'
		self.world = None
		self.__s = {} # subordinate areas; no dupes possible
		self.__t = {} # total data for data type, includes self and subordinates
	
	def areaFactory(self, name, lat=0.0, lon=0.0): 
		# factory class
		if (name in self.__s): return self.__s[name]
		ar = Area(self, name, lat, lon)
		if (type(ar) != Area): raise TypeError('Area added not of type \'Area\'')
		if (self.a['level'] == -1): raise UsageError('Parent level not set.')
		ar.a['level'] = self.a['level'] + 1
		ar.world = self.world
		if (ar.a['level'] > 1): ar.a['key'] = name + ', ' + self.a['key']
		self.__s[ar.name()] = ar
		return ar
		
	def areas(self):
		for k in sorted(self.__s.keys()):
			yield self.__s.get(k)
	
	def debug(self):
		for k in self.a:
			print('A' + str(self.a['level']) + ': ' + str(k) + ':' + str(self.a[k]))
		for k in self.__s:
			print('S' + str(self.a['level']) + ': ' + str(k) + ':' + str(self.__s[k]))
	
	def getList4ShapefileExport(self, area, data, n = 1, t = '?'):
		list = [n, area.a['fips'], area.a['adm3'], area.a['adm2'], area.a['adm1'], area.a['key'], area.a['lat'], area.a['lon'], t]
		list.extend(data)
		return list
	
	def getArea(self, name):
		if (name in self.__s): return self.__s[name]
		return None
	
	def getAreas(self):
		return self.__s
	
	def getData(self, label, thresh = 0, recalculate = False, ignore = False):
		# ignore parameter => ignore "unassigned", "out of", in a recalc
		# print('=================')
		# print('s.getData()', self.a['name'], label, self.world.lenData())
		# self.debug()
		# print('=================')
		if label not in self.__t or recalculate:
			self.__t[label] = np.zeros(self.world.lenData(), dtype = int)
			if (label in self.a): self.__t[label] += self.a[label]
			for a in self.areas(): # next level, e.g. 2 or 3, if it exists
				temp = a.getData(label, thresh, recalculate, ignore)
				#print('>>>', temp)
				if type(temp) == np.ndarray:
					if ignore == False or (a.name().startswith('Unassigned') == False and a.name().startswith('Out of') == False): 
						self.__t[label] += temp
				#a.debug()
				#print('-------------------------------------')
		# shift via thresh?
		if thresh > 0:
			i = np.argmax(self.__t[label] >= thresh) # index of first occurrence greater than thresh
			#print(self.__t[label], thresh, i)
			return self.__t[label][i:] # return slice starting from there
		return self.__t[label]
	
	def getDataThreshI(self, label, thresh = 0, recalculate = False, ignore = False):
		#print('=================')
		#print('s.getData()', self.a['name'], label, self.world.lenData())
		#self.debug()
		#print('=================')
		if label not in self.__t or recalculate:
			self.__t[label] = np.zeros(self.world.lenData(), dtype = int)
			if (label in self.a): self.__t[label] += self.a[label]
			for a in self.areas(): # next level, e.g. 2 or 3, if it exists
				temp = a.getData(label, thresh, recalculate, ignore)
				#print('>>>', temp)
				if type(temp) == np.ndarray:
					if ignore == False or (a.name().startswith('Unassigned') == False and a.name().startswith('Out of') == False): 
						self.__t[label] += temp
				#a.debug()
				#print('-------------------------------------')
		# shift via thresh?
		if thresh > 0:
			i = np.argmax(self.__t[label] >= thresh) # index of first occurrence greater than thresh
			return i # return slice starting from there
		return 0
	
	def getParent(self):
		return self.__parent
	
	def hasAreas(self):
		if (len(self.__s) > 0): return True
		return False
	
	def hasData(self, label):
		if (label in self.a): return True
		return False
	
	def key(self):
		return self.a['key']
	
	def level(self):
		return self.a['level']
	
	def name(self):
		return self.a['name']
	
	def numAreas(self):
		return len(self.__s)
	
	def setData(self, label, data, smooth = True):
		c_fixes = 0
		if smooth: c_fixes = Area.smooth(data)
		self.a[label] = data
		return c_fixes
	
	@staticmethod
	def smooth(data):
		c_fixes = 0
		# phase 1 (internal holes, until no more fixes)
		# smooth out holes [31, 71, 77, 0, 102] -> [31, 71, 77, 90, 102]
		while (True):
			n_fixes = 0
			for i in range(len(data)-2):
				if data[i] > 0 and data[i+1] == 0 and data[i+2] > 0:
					data [i+1] = int(round((data[i] + data[i+2]) / 2.0, 0))
					c_fixes += 1
					n_fixes += 1
			if n_fixes == 0: break
		# phase 2 (once, leading edge) [0, 0, 22] -> [0, 11, 22]
		for i in range(len(data)-2):
			if data[i] == 0 and data[i+1] == 0 and data[i+2] > 0:
				data [i+1] = int(round((data[i] + data[i+2]) / 2.0, 0))
				c_fixes += 1
		# phase 3 (internal negative adjustments; probably corrections to reported data, but we can smooth out)
		# [358 349 373] -> [358 365 373] # this is number of deaths in VA in the raw data and it's a cummulative total, so
		# this correction makes sense
		while (True):
			n_fixes = 0
			for i in range(len(data)-2):
				if data[i] > data[i+1] and data[i+2] > data[i] and data[i+2] > data[i+1]:
					data [i+1] = int(round((data[i] + data[i+2]) / 2.0, 0))
					c_fixes += 1
					n_fixes += 1
			if n_fixes == 0: break
		# return
		return c_fixes
	
	def __str__(self):
		s = self.a['name'] + '[' + str(self.a['level']) + ':' + str(len(self.__s)) + ']'
		return s

# world root area, which has no parent
class World(Area):
	
	def __init__(self, name='World', lat=0.0, lon=0.0):
		super().__init__(None, name, lat, lon)
		self.a['level'] = 0
		self.a['fips'] = 'N/A'
		self.__dates = [] # date data
		self.world = self
	
	def dump(self, filename):
		print('Saving World Cache [' + filename + ']...')
		pickle.dump(self, open(filename, 'wb'))
	
	def exportShapefile(self, filename):
		print('Exporting Shapefile [' + filename + ']...')
		w = shapefile.Writer(filename, shapefile.POINT)
		w.autoBalance = 1
		n = 0
		d = {} # data
		# create header
		dates = {} # dates
		d['DA'] = self.getDates()
		w.field('N','N')
		w.field('FIPS','C','5')
		w.field('ADM3','C','80')
		w.field('ADM2','C','80')
		w.field('ADM1','C','80')
		w.field('KEY','C','255')
		w.field('LAT','N',decimal=6)
		w.field('LON','N',decimal=6)
		w.field('T','C','1')
		for i in range(self.lenData()):
			dates[i] = d['DA'][i].strftime('%m/%d/%Y')
			w.field(dates[i], 'N')
		# proceed
		d['C'] = self.getData('CONFIRMED')
		d['D'] = self.getData('DEATHS')
		d['R'] = self.getData('RECOVERED')
		for t in ['C','D','R']: # area itself
			n += 1
			w.point(self.a['lon'], self.a['lat'])
			w.record(*self.getList4ShapefileExport(self, d[t], n, t))
		for s1 in self.areas():
			d['C'] = s1.getData('CONFIRMED')
			d['D'] = s1.getData('DEATHS')
			d['R'] = s1.getData('RECOVERED')
			for t in ['C','D','R']:
				n += 1
				w.point(s1.a['lon'], s1.a['lat'])
				w.record(*s1.getList4ShapefileExport(s1, d[t], n, t))
			for s2 in s1.areas():
				d['C'] = s2.getData('CONFIRMED')
				d['D'] = s2.getData('DEATHS')
				d['R'] = s2.getData('RECOVERED')
				for t in ['C','D','R']:
					n += 1
					w.point(s2.a['lon'], s2.a['lat'])
					w.record(*s2.getList4ShapefileExport(s2, d[t], n, t))
				for s3 in s2.areas():
					d['C'] = s3.getData('CONFIRMED')
					d['D'] = s3.getData('DEATHS')
					d['R'] = s3.getData('RECOVERED')
					for t in ['C','D','R']:
						n += 1
						w.point(s3.a['lon'], s3.a['lat'])
						w.record(*s3.getList4ShapefileExport(s3, d[t], n, t))
		# write the file
		w.close()
		# create the PRJ file
		prj = open("%s" % filename.replace('.shp','.prj'), "w")
		epsg = 'GEOGCS["WGS 84",'
		epsg += 'DATUM["WGS_1984",'
		epsg += 'SPHEROID["WGS 84",6378137,298.257223563]]'
		epsg += ',PRIMEM["Greenwich",0],'
		epsg += 'UNIT["degree",0.0174532925199433]]'
		prj.write(epsg)
		prj.close()
	
	def exportStandard(self, filename):
		print('Exporting (Standard) World [' + filename + ']...')
		fileout = open(filename,'w')
		n = 0
		d = {} # data
		d['DA'] = self.getDates()
		s = 'N|FIPS|ADM3|ADM2|ADM1|KEY|LAT|LON|T'
		for i in range(self.lenData()):
			s += '|' + d['DA'][i].strftime('%m/%d/%Y')
		fileout.write(s + '\n')
		d['C'] = self.getData('CONFIRMED')
		d['D'] = self.getData('DEATHS')
		d['R'] = self.getData('RECOVERED')
		for t in ['C','D','R']:
			n += 1
			s = str(n) + '|' + self.a['fips'] + '|N/A|N/A|N/A|' + self.a['key'] + '|' + str(self.a['lat']) + '|' + \
				str(self.a['lon']) + '|' + t
			for i in range(self.lenData()):
				s += '|' + str(d[t][i])
			fileout.write(s + '\n')
		for s1 in self.areas():
			d['C'] = s1.getData('CONFIRMED')
			d['D'] = s1.getData('DEATHS')
			d['R'] = s1.getData('RECOVERED')
			for t in ['C','D','R']:
				n += 1
				s = str(n) + '|' + s1.a['fips'] + '|' + s1.a['adm3'] + '|' + s1.a['adm2'] + '|' + s1.a['adm1'] + '|' + \
					s1.a['key'] + '|' + str(s1.a['lat']) + '|' + str(s1.a['lon']) + '|' + t
				for i in range(self.lenData()):
					s += '|' + str(d[t][i])
				fileout.write(s + '\n')
			for s2 in s1.areas():
				d['C'] = s2.getData('CONFIRMED')
				d['D'] = s2.getData('DEATHS')
				d['R'] = s2.getData('RECOVERED')
				for t in ['C','D','R']:
					n += 1
					s = str(n) + '|' + s2.a['fips'] + '|' + s2.a['adm3'] + '|' + s2.a['adm2'] + '|' + s2.a['adm1'] + '|' + \
						s2.a['key'] + '|' + str(s2.a['lat']) + '|' + str(s2.a['lon']) + '|' + t
					for i in range(self.lenData()):
						s += '|' + str(d[t][i])
					fileout.write(s + '\n')
				for s3 in s2.areas():
					d['C'] = s3.getData('CONFIRMED')
					d['D'] = s3.getData('DEATHS')
					d['R'] = s3.getData('RECOVERED')
					for t in ['C','D','R']:
						n += 1
						s = str(n) + '|' + s3.a['fips'] + '|' + s3.a['adm3'] + '|' + s3.a['adm2'] + '|' + s3.a['adm1'] + '|' + \
							s3.a['key'] + '|' + str(s3.a['lat']) + '|' + str(s3.a['lon']) + '|' + t
						for i in range(self.lenData()):
							s += '|' + str(d[t][i])
						fileout.write(s + '\n')
		fileout.close()
	
	def exportTransposed(self, filename):
		print('Exporting (Transposed) World [' + filename + ']...')
		fileout = open(filename,'w')
		n = 0
		d = {} # data
		d['DA'] = self.getDates()
		fileout.write('N|FIPS|ADM3|ADM2|ADM1|DATE|KEY|LAT|LON|CONFIRMED|DEATHS|RECOVERED\n')
		d['C'] = self.getData('CONFIRMED')
		d['D'] = self.getData('DEATHS')
		d['R'] = self.getData('RECOVERED')
		for i in range(self.lenData()):
			n += 1
			s = str(n) + '|' + self.a['fips'] + '|N/A|N/A|N/A|' + d['DA'][i].strftime('%m/%d/%Y') + '|' + self.a['key'] + \
				'|' + str(self.a['lat']) + '|' + str(self.a['lon']) + '|' + str(d['C'][i]) + '|' + str(d['D'][i]) + \
				'|' + str(d['R'][i])
			fileout.write(s + '\n')
		for s1 in self.areas():
			d['C'] = s1.getData('CONFIRMED')
			d['D'] = s1.getData('DEATHS')
			d['R'] = s1.getData('RECOVERED')
			for i in range(self.lenData()):
				n += 1
				s = str(n) + '|' + s1.a['fips'] + '|' + s1.a['adm3'] + '|' + s1.a['adm2'] + '|' + s1.a['adm1'] + \
					'|' + d['DA'][i].strftime('%m/%d/%Y') + '|' + s1.a['key'] + '|' + \
					str(s1.a['lat']) + '|' + str(s1.a['lon']) + '|' + str(d['C'][i]) + '|' + str(d['D'][i]) + '|' + str(d['R'][i])
				fileout.write(s + '\n')
			for s2 in s1.areas():
				d['C'] = s2.getData('CONFIRMED')
				d['D'] = s2.getData('DEATHS')
				d['R'] = s2.getData('RECOVERED')
				for i in range(self.lenData()):
					n += 1
					s = str(n) + '|' + s2.a['fips'] + '|' + s2.a['adm3'] + '|' + s2.a['adm2'] + '|' + s2.a['adm1'] + \
						'|' + d['DA'][i].strftime('%m/%d/%Y') + '|' + s2.a['key'] + '|' + \
						str(s2.a['lat']) + '|' + str(s2.a['lon']) + '|' + str(d['C'][i]) + '|' + str(d['D'][i]) + '|' + str(d['R'][i])
					fileout.write(s + '\n')
				for s3 in s2.areas():
					d['C'] = s3.getData('CONFIRMED')
					d['D'] = s3.getData('DEATHS')
					d['R'] = s3.getData('RECOVERED')
					for i in range(self.lenData()):
						n += 1
						s = str(n) + '|' + s3.a['fips'] + '|' + s3.a['adm3'] + '|' + s3.a['adm2'] + '|' + s3.a['adm1'] + \
							'|' + d['DA'][i].strftime('%m/%d/%Y') + '|' + s3.a['key'] + '|' + \
							str(s3.a['lat']) + '|' + str(s3.a['lon']) + '|' + str(d['C'][i]) + '|' + str(d['D'][i]) + '|' + str(d['R'][i])
						fileout.write(s + '\n')
		fileout.close()
	
	# return array of indices from the dates, e.g. [0, 1, 2, 3, 4...]
	def getIndexR(self, shift = 0):
		# eg shift = 1, means array will start with 1 e.g. [1, 2, 3, 4...] but be of same length
		temp = np.arange(len(self.__dates))
		if shift == 0: return temp
		temp += shift
		return temp
	
	def getDates(self):
		return self.__dates
	
	def lenData(self):
		return len(self.__dates)
	
	@staticmethod
	def load(filename):
		return pickle.load(open(filename, 'rb'))
	
	def setDates(self, startDate, length):
		self.__dates = [datetime.now() for i in range(length)]
		self.__dates[0] = startDate
		for i in range(1, length):
			self.__dates[i] = self.__dates[i-1] + timedelta(days=1)

# tests
if __name__ == '__main__':
	w = World()
	c = w.areaFactory('Australia', 25.2744, 133.7751)
	print(c)
	print(c.name())
	print(c.numAreas())
	s = c.areaFactory('Tasmania', -41.4545, 145.9707)
	print(s, s.name(), s.lat())
	print('#####')
	print(c.numAreas())
	s = c.areaFactory('Victoria', -37.8136, 144.9631)
	print(c.numAreas())
	print(c.lat())
	print('=====')
	for s in c.areas():
		print(s)
	print('=====')
	c = w.areaFactory('Canada', 53.9333, -116.5765)
	s = c.areaFactory('Alberta', 53.9333, -116.5765)
	s = c.areaFactory('Alberta', 53.9333, -116.5765)
	s = c.areaFactory('Alberta', 53.9333, -116.5765)
	s = s.areaFactory('Smaller', 53.9333, -116.5765)
	s = s.areaFactory('Smallest', 53.9333, -116.5765)
	print('=====')
	for c in w.areas():
		print(str(c) + ' ' + c.key())
		for s1 in c.areas():
			print('1	' + str(s1) + ' ' + s1.key())
			for s2 in s1.areas():
				print('2		' + str(s2) + ' ' + s2.key())
				for s3 in s2.areas():
					print('3			' + str(s3) + ' ' + s3.key())
