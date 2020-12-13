#!/usr/bin/python

"""
	Main file
"""

import os, sys
import argparse

import numpy as np
import pandas as pd
import math
import random
import itertools
import time

from dl_func import *
from sits_func import *
from res_func import *

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.metrics import confusion_matrix
#from sklearn.externals import joblib
#above did not work for me, below does
import joblib
import csv
#for class imbalances
from imblearn.under_sampling import RandomUnderSampler


def save_minMaxVal(minmax_file, min_per, max_per):	
	with open(minmax_file, 'w') as f:
		writer = csv.writer(f, delimiter=',')
		writer.writerow(min_per)
		writer.writerow(max_per)


#-----------------------------------------------------------------------
#-----------------------------------------------------------------------
#---------------------			MAIN			------------------------
#-----------------------------------------------------------------------
#-----------------------------------------------------------------------

#-----------------------------------------------------------------------		
def main(classifier_type, train_file, test_file, modelfn, outdir, balanced):

	classif_type = ["RF", "TempCNN", "GRU-RNNbi", "GRU-RNN"]
	if classifier_type not in classif_type:
		print("ERR: select an available classifier (RF, TempCNN, GRU-RNNbi or GRU-RNN)")
		sys.exit(1)
	
	dl_flag = True
	if classifier_type == "RF":
		dl_flag = False

	# Parameters
	#-- general
	#nchannels = 10
	nchannels= 4
	#-- deep learning
	n_epochs = 20
	#batch_size = 64
	batch_size = 16
	val_rate = 0.1
	
	# Reading SITS
	X_train, pid_train, y_train = readSITSData(train_file)
	X_test, pid_test, y_test = readSITSData(test_file)
	nclasses = len(np.unique(y_train))
	print(np.unique(y_train).value_counts())
	print(np.unique(y_test).value_counts())
	print(len(y_train))
	print(len(y_test))

	print(X_train.shape)

	if balanced:
		print('balancing')

		undersample = RandomUnderSampler(sampling_strategy='majority', random_state=42)
		X_train, y_train = undersample.fit_resample(X_train, y_train)
		pid_train = pid_train[undersample.sample_indices_]
	
	print(X_train.shape)

	
	# Evaluated metrics
	if classifier_type=="RF":
		eval_label = ['OA', 'OOB_error', 'train_time', 'test_time', 'RMSE']
	else:
		eval_label = ['OA', 'train_loss', 'train_time', 'test_time']
	
	# Output filenames
	res_file = os.path.join(outdir,'resultOA-' + classifier_type + '.csv')
	res_mat = np.zeros((len(eval_label),1))
	model_file = os.path.join(outdir,modelfn)
	#model_file = os.path.join(outdir,'/model-' + classifier_type + '.h5')
	conf_file = os.path.join(outdir,'confMatrix-' + classifier_type + '.csv')
	acc_loss_file = os.path.join(outdir,'trainingHistory-'+ classifier_type + '.csv') #-- only for deep learning models
	
	if os.path.isfile(res_file):
		print("ERR: result file already exists")
		sys.exit(1)
	
	# Training	
	if dl_flag:			#-- deep learning approaches
		#---- Pre-processing train data
		X_train = reshape_data(X_train, nchannels)
		min_per, max_per = computingMinMax(X_train)
		#saving minmax file for write output
		minMaxVal_file = '.'.join(model_file.split('.')[0:-1])
		minMaxVal_file = minMaxVal_file + '_minMax.txt'
		min_per, max_per = computingMinMax(X_train)
		save_minMaxVal(minMaxVal_file, min_per, max_per)

		print(y_train.shape)
		print(y_test.shape)
		print(nclasses)

		X_train =  normalizingData(X_train, min_per, max_per)
		y_train_one_hot = to_categorical(y_train, nclasses)
		X_test = reshape_data(X_test, nchannels)
		X_test =  normalizingData(X_test, min_per, max_per)
		y_test_one_hot = to_categorical(y_test, nclasses)

		#---- Create a validation set if validation set required	
		if val_rate>0:
			print("Creating a validation set")
			unique_pid_train, indices = np.unique(pid_train, return_inverse=True) 
			nb_pols = len(unique_pid_train)
			ind_shuffle = list(range(nb_pols))
			random.shuffle(ind_shuffle)
			list_indices = [[] for i in range(nb_pols)]
			shuffle_indices = [[] for i in range(nb_pols)]
			[ list_indices[ind_shuffle[val]].append(idx) for idx, val in enumerate(indices)]
			final_ind = list(itertools.chain.from_iterable(list_indices))
			m = len(final_ind)
			final_train = int(math.ceil(m*(1.0-val_rate)))
			shuffle_pid_train = pid_train[final_ind]
			id_final_train = shuffle_pid_train[final_train]
			
			while shuffle_pid_train[final_train-1]==id_final_train:
				final_train = final_train-1
			final_train = int(final_train)
			X_val = X_train[final_ind[final_train:],:,:]
			y_val = y_train[final_ind[final_train:]]
			X_train = X_train[final_ind[:final_train],:,:]
			y_train = y_train[final_ind[:final_train]]

			print(X_train.shape)
			print(y_train.shape)
			#balancing dataset


			y_train_one_hot = to_categorical(y_train, nclasses)
			y_val_one_hot = to_categorical(y_val, nclasses)

		if 	classifier_type == "TempCNN":
			model = Archi_TempCNN(X_train, nclasses)
		elif classifier_type == "GRU-RNNbi":
			model = Archi_GRURNNbi(X_train, nclasses)
		elif classifier_type == "GRU-RNN":
			model = Archi_GRURNN(X_train, nclasses)	
			
			
		if val_rate==0:
			res_mat[0], res_mat[1], model, model_hist, res_mat[2], res_mat[3] = \
				trainTestModel(model, X_train, y_train_one_hot, X_test, y_test_one_hot, model_file, n_epochs=n_epochs, batch_size=batch_size)
		else:
			res_mat[0], res_mat[1], model, model_hist, res_mat[2], res_mat[3] = \
				trainTestValModel(model, X_train, y_train_one_hot, X_val, y_val_one_hot, X_test, y_test_one_hot, model_file, n_epochs=n_epochs, batch_size=batch_size)
		
		saveLossAcc(model_hist, acc_loss_file)		
		p_test = model.predict(x=X_test)
		#---- computing confusion matrices
		C = computingConfMatrix(y_test, p_test, nclasses)
						
		print('Overall accuracy (OA): ', res_mat[0])
		print('Train loss: ', res_mat[1])
		print('Training time (s): ', res_mat[2])
		print('Test time (s): ', res_mat[3])
		
				
	else:
		rf = RandomForestClassifier(n_estimators=100, max_features='sqrt',
				max_depth=25, min_samples_split=2, oob_score=True, n_jobs=-1, verbose=1)
			
		#-- train a rf classifier
		start_train_time = time.time()				
		rf.fit(X_train, y_train)
		res_mat[2] = round(time.time()-start_train_time, 2)
		print('Training time (s): ', res_mat[2,0])
			
		#-- save the model
		joblib.dump(rf, model_file)
		print("Writing the model over")
			
		#-- prediction
		start_test_time =  time.time()
		predicted = rf.predict(X_test)
		res_mat[3] = round(time.time()-start_test_time, 2)
		print('Test time (s): ', res_mat[3,0])

		importances = rf.feature_importances_
		indices = np.argsort(importances)[::-1]

		# Print the feature ranking
		print("Feature ranking:")


		for f in range(X_train.shape[1]):
		#for f in range(X_train.shape[1]):
			print("%d. feature %d (%f)" % (f + 1, indices[f], importances[indices[f]]))
		#print(importances)	
		
		#-- OA and OA_OOB
		res_mat[0] = accuracy_score(y_test, predicted)
		res_mat[1] = rf.oob_score_
		
		#-- RMSE
		nbTestInstances = y_test.shape[0]
		p_test = rf.predict_proba(X_test)
		y_test_one_hot = np.eye(nclasses)[y_test]
		diff_proba = y_test_one_hot - p_test
		rmse = math.sqrt(np.sum(diff_proba*diff_proba)/nbTestInstances)
		res_mat[4] = rmse
				
		#-- compute confusion matrix
		C = confusion_matrix(y_test, predicted)							
		
		print('Overall accuracy (OA): ', res_mat[0])
		print('Out-of-bag score estimate (OA_OOB): ', res_mat[1])
		print('Training time (s): ', res_mat[2])
		print('Test time (s): ', res_mat[3])
		print('RMSE: ', res_mat[4])
	
	
	# Saving CM and summary res file
	#---- saving the confusion matrix
	#class_label = ["cl0"]
	class_label = []
	for add in range(nclasses):
		class_label.append("cl"+str(add))
	save_confusion_matrix(C, class_label, conf_file)
	#---- saving res_file
	saveMatrix(np.transpose(res_mat), res_file, eval_label)
	
	
#-----------------------------------------------------------------------		
if __name__ == "__main__":
	try:
		if len(sys.argv) == 1:
			prog = os.path.basename(sys.argv[0])
			print('      '+sys.argv[0]+' [options]')
			print("     Help: ", prog, " --help")
			print("       or: ", prog, " -h")
			print("example 1 : python %s --classifier TempCNN " %sys.argv[0])
			sys.exit(-1)
		else:
			parser = argparse.ArgumentParser(description='Training RF, TempCNN or GRU-RNN models on SITS datasets')
			parser.add_argument('--classifier', dest='classifier',
								help='classifier to train (RF/TempCNN/GRU-RNNbi/GRU-RNN)')
			parser.add_argument('--train', dest='train_file',
								help='training file')
			parser.add_argument('--test', dest='test_file',
								help='test_file')
			parser.add_argument('--modelfilename', dest='modelfn')
			parser.add_argument('--outdir', dest='outdir')
			parser.add_argument('--balanced', dest='balanced')

			args = parser.parse_args()
			if not os.path.exists(args.outdir):
				os.makedirs(args.outdir)
			balanced = bool(int(args.balanced))
			main(args.classifier, args.train_file, args.test_file, args.modelfn,args.outdir, balanced)
			print("0")
	except(RuntimeError):
		print >> sys.stderr
		sys.exit(1)




#EOF
