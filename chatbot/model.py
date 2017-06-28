# coding: utf-8


# from data_utils import load, balance_dataset

import numpy as np
from sklearn import naive_bayes
from sklearn.metrics import roc_auc_score, accuracy_score, confusion_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cross_validation import train_test_split
from nltk.corpus import stopwords
import cPickle
import os

from collections import Counter

def fit_and_save(model_path="model/classifier.pkl", vect_path="model/vectorizer.pkl"):
    """
        This function fits the classifier and stores the object in 'model_path'
    """
    raw_sentences, labels = load(only="raw") # gets raw data in form of string sentences, and its labels
    stopset = set(stopwords.words("english"))
    vectorizer = TfidfVectorizer(use_idf=True, strip_accents="ascii", stop_words=stopset) # fit vectorizer

    # since we are facing an unbalanced dataset (400k positive sentences vs 20k negative sentences)
    # we need to balance the dataset to get a 50%/50% pos/neg distribution.
    #raw_sentences, labels = balance_dataset(raw_sentences, labels)
    print Counter(labels)

    X = vectorizer.fit_transform(raw_sentences)
    print X.shape
    #  split data into train/test
    X_train, X_test, y_train, y_test = train_test_split(X, labels)

    # fit classifier
    clf = naive_bayes.MultinomialNB()
    clf.fit(X_train, y_train)

    # print accuracy and roc auc scores
    print "-"*15, "PERFORMANCE METRICS","-"*15
    print "AUC Score:", roc_auc_score(y_test, clf.predict_proba(X_test)[:,1])
    print "Accuracy: ", accuracy_score(y_test, np.argmax(clf.predict_proba(X_test),axis=1))
    print "Confusion matrix"
    print confusion_matrix(y_test, np.argmax(clf.predict_proba(X_test),axis=1))
    print

    print "Saving vectorizer to", vect_path
    print "Saving model to", model_path

    with open(model_path, "wb") as f:
        cPickle.dump(clf, f)
    with open(vect_path, "wb") as f:
        cPickle.dump(vectorizer, f)

def load_model_and_vectorizer(model_path="model/classifier.pkl", vect_path="model/vectorizer.pkl"):

    if os.path.isfile(model_path) and os.path.isfile(vect_path):
        clf = None
        vect = None
        with open(model_path, "rb") as f:
            clf = cPickle.load(f)
        with open(vect_path, "rb") as f:
            vect = cPickle.load(f)
        return clf, vect
    else:
        print "Model Error: No model found in %s or %s" % (str(model_path), str(vect_path))

if __name__=="__main__":
    fit_and_save()
