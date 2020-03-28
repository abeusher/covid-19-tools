#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# curve fit model and graphics support
#
import numpy as np
from scipy.optimize import curve_fit 
import sys
from matplotlib import pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import time
import statsmodels.formula.api as smf

class Error(Exception):
	# Base class for exceptions in this module.
	pass

def model_exp(x, a, b):
	y = a*np.exp(b*x)
	return y

def model_sigmoid(x, a, b):
	y = 1 / (1 + np.exp(-b*(x-a)))
	return y

# def model_poly3(x_data, a, b, c):
	# y = 1
	# return y

def fit(x_data, y_data, model_type = 'EXP'):
	if (model_type == 'EXP'):
		p0 = [1,1] # on day 1, 1 case -> hint for the curve fit
		popt, pcov = curve_fit(model_exp, x_data, y_data, p0)
		perr = np.sqrt(np.diag(pcov))
		# residual sum of squares
		residuals = y_data - model_exp(x_data, *popt)
		ss_res = np.sum(residuals**2)
		# total sum of squares
		ss_tot = np.sum((y_data-np.mean(y_data))**2)
		# r-squared
		rsqd = round(1 - (ss_res / ss_tot), 4)
		return popt, pcov, perr, rsqd
	elif (model_type == 'SIGMOID'):
		p0 = [1,1] # on day 1, 1 case -> hint for the curve fit
		popt, pcov = curve_fit(model_sigmoid, x_data, y_data, p0)
		perr = np.sqrt(np.diag(pcov))
		# residual sum of squares
		residuals = y_data - model_sigmoid(x_data, *popt)
		ss_res = np.sum(residuals**2)
		# total sum of squares
		ss_tot = np.sum((y_data-np.mean(y_data))**2)
		# r-squared
		rsqd = round(1 - (ss_res / ss_tot), 4)
		return popt, pcov, perr, rsqd
	else: # POLY3
		weights = np.polyfit(x_data, y_data, 3)
		model = np.poly1d(weights)
		results = smf.ols(formula='y ~ model(x)', data=x_data).fit()
		return weights, model, results

def calculate(d_data, y_data, n_forecast, title, label, model_type = 'EXP'):
	# d_data: list of dates in datetime format, sorted
	# y_data: list of numbers (e.g. covid cases) of same length for each date
	# n_forecast: number of days to forecast
	# label: eg 'cases'
	# model_type EXP, SIGMOID, POLY3
	# NOTE: only EXP presently works
	
	# check model_type
	if (isinstance(model_type, str) == False):
		model_type = str(model_type)
	model_type = model_type.upper()
	if (model_type != 'EXP' and model_type != 'SIGMOID' and model_type != 'POLY3'):
		model_type = 'EXP'
	
	if (len(d_data) != len(y_data)):
		raise Error('d_data and y_data have unequal lengths.')
	size = len(d_data)
	x_data = np.array([i for i in range(size)]) # date integer data

	# print('y_data:')
	# print(y_data)
	# print('d_data:')
	# print(d_data)

	# generate derivative clone without missing values
	xd_data = np.copy(x_data)
	yd_data = np.copy(y_data)
	removal_list = []
	for i in range(size):
		if (y_data[i] == -1):
			removal_list.append(i)
	xd_data = np.delete(xd_data, removal_list)
	yd_data = np.delete(yd_data, removal_list)
	
	# curve fit
	if (model_type == 'EXP' or model_type == 'SIGMOID'):
		popt, pcov, perr, rsqd = fit(xd_data, yd_data, model_type)
	else: # POLY3
		weights, model, results = fit(xd_data, yd_data, model_type)
	
	# calc ALL curve fit values for 0 thru n-day forecast -> our trajectory
	xm_data = np.array([i for i in range(size + n_forecast)])
	if (model_type == 'EXP'):
		ym_data = model_exp(xm_data, *popt)
	elif (model_type == 'SIGMOID'):
		ym_data = model_sigmoid(xm_data, *popt)
	else: # POLY3
		results = smf.ols(formula='y ~ model(x)', data=xm_data).fit()
		print(results)
	
	# set curve fit values for missing data; useful for visualization
	xh_data = np.copy(xm_data)
	yh_data = np.copy(ym_data)
	removal_list = []
	for i in range(size):
		if (y_data[i] != -1):
			removal_list.append(i)
	xh_data = np.delete(xh_data, removal_list)
	yh_data = np.delete(yh_data, removal_list)
	
	# set curve fit values for projected data; useful for visualization
	xp_data = np.copy(xm_data)
	yp_data = np.copy(ym_data)
	removal_list = []
	for i in range(size):
		if (i < size):
			removal_list.append(i)
	xp_data = np.delete(xp_data, removal_list)
	yp_data = np.delete(yp_data, removal_list)
	
	# generate range of dates
	df_data = np.array([d_data[0] + timedelta(days=i) for i in range(size + n_forecast)])
	
	# generate plot
	fig, ax = plt.subplots()
	#ax = fig.add_subplot(111)
	ax.set_ylim(0,(np.amax(ym_data)*1.07))
	plot_label = 'Model'
	if (model_type == 'EXP'):
		plot_label += ' (r^2 = ' + str(rsqd) + ')'
	ax.plot(xm_data, ym_data, '--', color ='darkgrey', label = plot_label)
	ax.plot(xd_data, yd_data, 'o', color ='red', label ='Reported Open ' + label)
	ax.plot(xh_data, yh_data, 'o', color ='black', label ='Historical Estimate') 
	ax.plot(xp_data, yp_data, 'o', color ='blue', label ='Projected Estimate') 
	ax.legend()
	ax.set_title(title, fontsize=18, horizontalalignment='center')
	ax.set_xlabel('# Days + ' + d_data[0].strftime('%m/%d/%Y'), fontsize=12)
	ax.set_ylabel('# ' + label, fontsize=12)
	ax.grid(color='gray', linestyle='dotted', linewidth=0.5)
	for i,j in zip(xh_data,yh_data):
		c = 'black'
		if (i >= (size-1)):
			c = 'blue'
		ax.text(i-0.1, j+3, str(int(round(j, 0))), fontsize=8, \
		horizontalalignment='right', color=c)
	# initial value
	if (y_data[0] != -1):
		ax.text(xd_data[0]-0.1, yd_data[0]+3, str(int(round(yd_data[0], 0))), fontsize=8, \
		horizontalalignment='right', color='red')
	else:
		ax.text(xh_data[0]-0.1, yh_data[0]+3, str(int(round(yh_data[0], 0))), fontsize=8, \
		horizontalalignment='right', color='black')
	#ax2 = ax.twinx()  # instantiate a second axes that shares the same x-axis
	#ax2.set_xlim(df_data[0], df_data[size])
	# x_data = mdates.date2num(dates)
	#fig.tight_layout()
	return plt, popt, rsqd