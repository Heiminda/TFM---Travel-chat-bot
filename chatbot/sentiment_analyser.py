# coding: utf-8


import numpy as np
import cPickle
import nltk
from unidecode import unidecode
from nltk.tokenize import sent_tokenize, word_tokenize
from pprint import pprint # pretty-print

import model
from difflib import SequenceMatcher

def sequence_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

class SentimentAnalyser(object):

    def __init__(self, clf, vectorizer, criteria_file):
        self.clf  = clf
        self.vectorizer = vectorizer
        self.text = None
        self.criteria, self.reverse_criteria = self.parse_criteria(criteria_file)
        self.criteria_tuples, self.reverse_criteria_tuples = self.build_criteria_tuples()

    def parse_criteria(self, fname):
        # see criteria file format
        with open(fname, "r") as f:
            lines = f.readlines()
        criterias = {line.split(":")[0]:line.rstrip().split(":")[1].split(",") for line in lines}
        # get reverse dict (reverse mapping)
        reverse_criterias = dict()
        for topic, words in criterias.iteritems():
            for word in words:
                reverse_criterias[word] = topic
        return criterias, reverse_criterias

    def build_criteria_tuples(self):
        # this function justs transform the dictionary into a list of tuples (key,value)
        rc_tuples = zip(self.reverse_criteria.keys(),self.reverse_criteria.values())
        c_tuples = []
        for topic, words in self.criteria.iteritems():
            for w in words:
                c_tuples.append((topic,w))
        return c_tuples,rc_tuples

    def print_criteria(self):
        pprint(self.criteria)

    def set_text_to_analyse(self, text):
        if len(text)>0:
            self.text = unidecode(str(text).lower())
            self.sentences = sent_tokenize(self.text)
        else:
            raise ArgumentError("text argument has no length!")

    def predict_proba(self, text):
        txt_to_test = np.array([text])
        vector = self.vectorizer.transform(txt_to_test)
        return self.clf.predict_proba(vector)

    def predict(self, text):
        return np.argmax(self.predict_proba(text))

    def analyse(self, text, confidence=0.575):

        result_string = "\nSEMANTIC ANALYSER RESULTS\n\n" # string result to print
        result_dict   = dict()

        result_dict["content"] = text

        # set text to analyse and get sentences
        self.set_text_to_analyse(text)

        # predict overall sentiment of text
        overall_sentiment_proba = self.predict_proba(self.text)
        overall_sentiment = self.predict(self.text)
        result_dict["sentiment"] = "positive" if overall_sentiment == 1 else "negative"
        result_dict["confidence"] = round(max(overall_sentiment_proba[0,:]),2)

        if overall_sentiment == 1:
            overall_sentiment_string = "Positive (%2.2f%% confidence)" % (overall_sentiment_proba[:,1][0]* float(100))
        else:
            overall_sentiment_string = "Negative (%2.2f%% confidence)" % (overall_sentiment_proba[:,0][0] * float(100))
        result_string += "\tOverall sentiment:\t%s" %  overall_sentiment_string

        # compute review score
        score = 0
        sentence_topics = [] # list of list of tuples containing (topic, sentiment(0/1))
        result_string += "\n\n\tSentence analysis: (we only analyse if confidence %% > %2.2f%%)" % confidence

        for sentence in self.sentences:

            # get sentiment prediction
            p = self.predict_proba(sentence)

            # add info to print
            result_string += "\n\n\t\tSentence: %s..." % sentence[:int(len(sentence)*0.25)] # show small part of sentence
            if np.argmax(p) == 1:
                result_string += "\t(Positive %2.2f%%)" % (p[:,1][0]* float(100))
            else:
                result_string += "\t(Negative %2.2f%%)" % (p[:,0][0]* float(100))

            # if prediction confidence is not enough (at least it should be 60%), we skip that sentence
            if np.max(p, axis=1) < confidence:
                continue
            p = np.argmax(p, axis=1)

            # tokenize words in sentence and then get sentence topics
            topics = self.get_sentence_topics(word_tokenize(sentence))

            # add topics encountered to print
            result_string += "\n\t\tTopics: %s" % (",".join(topics))
            # assign the sentiment to those topics
            topics_labeled = zip(topics, list(-np.ones(len(topics)).astype(np.int32)) if p == 0 else list(np.ones(len(topics)).astype(np.int32)))
            sentence_topics.extend(topics_labeled)

            # assign score depending on how much topics encountered and its sentiment
            for topic,sentiment in topics_labeled:
                # assign score depending on sentiment
                if sentiment == 1:
                    score += 1
                else:
                    score -= 1

        result_dict["topics"] = sentence_topics
        result_dict["score"] = score
        result_string += "\n\n\n\tFinal topics:\n\t\t"
        result_string += "\n\n\t\t".join([topic + "\t\t" + "Positive (+1)" if sent == 1 else topic + "\t\t" + "Negative (-1)" for topic,sent in sentence_topics])
        result_string += "\n\n\tFinal text score:\t\t%d" % score

        return result_string, result_dict


    def get_sentence_topics(self, sentence, threshold=0.85):
        # threshold = parameter to filter down similarity percentage between words
        # higher value will yield less matches with sentence's words
        # lower value will accept more matches
        topics = []
        for word in sentence:
            # get similarity of word with all words, if one gets high score we break
            similarities = map(lambda w: sequence_similarity(word, w[0]), self.reverse_criteria_tuples)
            if max(similarities) >= threshold:
                best_match = self.reverse_criteria_tuples[np.argmax(similarities)][0] # get best match word
                # assign topic, but be careful since same topic words can be mentioned more than once in sentence
                topic = self.reverse_criteria[best_match]
                if topic not in topics:
                    topics.append(topic)
        # if no topic was identified in sentence, we just pass "unknown"
        if len(topics) == 0:
            topics.append("unknown")
        return topics
