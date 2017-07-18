from datetime import date
from enum import IntEnum
from gzip import GzipFile
from logging import basicConfig, DEBUG, debug
from os.path import join as path_join
from pickle import load, dump
from random import shuffle
from sys import stdout
from typing import Tuple

from numpy import uint64, ndarray, hstack
from numpy import zeros, array
from pandas import read_csv, Series, Index

from create_sentiment_featuresets import DATA_DIR, create_lexicon, process_sample, lemmatizer, reallocate_ndarray, tqdm

basicConfig(level=DEBUG, stream=stdout)

max_lines = int(1e7)

pickle_filepath = path_join(DATA_DIR, "sentiment_large_data.pickle")


class Polarity(IntEnum):
    NEGATIVE = 0
    NEUTRAL = 2
    POSITIVE = 4


column_names_ = ['polarity', 'id', 'datetime', 'query', 'user', 'text']
record_index = Index(column_names_)
column_dtypes = {'polarity': Polarity, 'id': uint64, 'datetime': date, 'query': str, 'user': str, 'text': str}
columns_to_use_ = ['polarity', 'text']


def get_iter(input_filename, column_names=column_names_, columns_to_use=columns_to_use_):
    input_filepath = path_join(DATA_DIR, input_filename)
    return read_csv(input_filepath, names=column_names, usecols=columns_to_use, chunksize=int(1e4),
                    encoding='latin-1')  # , compression='zip'


def process_line(line, lexicon) -> Tuple[ndarray, ndarray]:
    record_data = line[1:-1].split("\",\"")  # eliminate all delimiting commas and quotation marks
    record = Series(record_data, index=record_index)  # .astype(column_dtypes)
    polarity_value = int(record.polarity)
    if Polarity(polarity_value) not in {Polarity.POSITIVE, Polarity.NEGATIVE}:
        raise ValueError("invalid polarity value %d" % polarity_value)
    words = process_sample(record.text)

    words = [lemmatizer.lemmatize(word) for word in words]
    # words = [lemmatizer.lemmatize(word) for word in tqdm(words, desc="lemmatizing", unit="word")]

    # vectorize
    features = zeros(len(lexicon))
    for word in words:
        # for word in tqdm(words, desc="vectorizing", unit="word"):
        if word in lexicon:
            index_of_word_in_lexicon = lexicon.index(word)
            features[index_of_word_in_lexicon] += 1

    label = array([1, 0]) if (record.polarity == Polarity.POSITIVE) else array([0, 1])
    return features, label


def create_design_matrix(samples_filename, lexicon: list):
    """
    In-memory
    :param samples_filename:
    :param lexicon:
    :return:
    """
    design_matrix = []  # list of features+label pairs
    with open(samples_filename) as file:
        contents = file.readlines()
        for line in tqdm(contents, desc="creating design matrix from %s" % samples_filename, unit="line"):
            try:
                features, label = process_line(line, lexicon)
            except ValueError:
                continue
            design_matrix.append([features, label])
            if len(design_matrix) == max_lines:
                break

    shuffle(design_matrix)
    design_matrix = array(design_matrix)

    x, y = design_matrix[:, 0], design_matrix[:, 1]

    return reallocate_ndarray(x), reallocate_ndarray(y),


def write_design_matrix(samples_filepath, design_matrix_filepath, lexicon: list):
    """
    On-disk
    :param samples_filepath:
    :param design_matrix_filepath:
    :param lexicon:
    :return:
    """
    with GzipFile(design_matrix_filepath + ".gz", 'a') as outzipfile:
        with open(samples_filepath) as infile:
            n_lines_written = 0
            contents = infile.readlines()
            for line in tqdm(contents, desc="creating design matrix from %s" % samples_filepath, unit="line"):
                try:
                    features, label = process_line(line, lexicon)
                except ValueError:
                    continue
                sample_row = hstack((features, label))
                if n_lines_written == max_lines:
                    break
                sample_row.tofile(outzipfile)
                n_lines_written += 1

                # TODO: shuffle


def generate_design_matrix(samples_filepath, lexicon: list, max_lines_=max_lines):
    """
    Online
    :param max_lines_:
    :param samples_filepath:
    :param lexicon:
    :return:
    """
    with open(samples_filepath) as infile:
        n_lines_written = 0
        contents = infile.readlines()
        for line in tqdm(contents, desc="creating design matrix from %s" % samples_filepath, unit="line"):
            if n_lines_written == max_lines_:
                break
            try:
                features, label = process_line(line, lexicon)
            except ValueError:
                continue
            n_lines_written += 1
            yield (features, label)

            # TODO: shuffle


def get_paths_and_lexicon(train_filename="training.1600000.processed.noemoticon.csv",
                          test_filename="testdata.manual.2009.06.14.csv"):
    train_filepath = path_join(DATA_DIR, train_filename)
    test_filepath = path_join(DATA_DIR, test_filename)
    lexicon = load_or_create_lexicon(train_filename)
    return train_filepath, test_filepath, lexicon


def pickle_processed_data():
    train_filename = "training.1600000.processed.noemoticon.csv"
    test_filename = "testdata.manual.2009.06.14.csv"

    # x_train, y_train = clean_split_design_matrix(train_filename)
    # x_test, y_test = clean_split_design_matrix(test_filename)
    #
    # x_train, lexicon = x_train.str.get_dummies()
    # x_test.apply(lambda text: set(map(lambda word: word if word in lexicon else None, text.split())))

    train_filepath = path_join(DATA_DIR, train_filename)
    test_filepath = path_join(DATA_DIR, test_filename)
    lexicon = load_or_create_lexicon(train_filename)
    # x_test, y_test = create_design_matrix(test_filepath, lexicon)  # faster than train dataset (fail-fast)
    # x_train, y_train = create_design_matrix(train_filepath, lexicon)  # 3 minutes
    #
    # with open(pickle_filepath, "wb") as pickle_file:
    #     dump([x_train, y_train, x_test, y_test], pickle_file)
    write_design_matrix(test_filepath, '.'.join((test_filepath, "vectorized", "csv")), lexicon)
    write_design_matrix(train_filepath, '.'.join((train_filepath, "vectorized", "csv")), lexicon)


def load_or_create_lexicon(train_filename):
    lexicon_filename = train_filename + ".lexicon.pickle"
    lexicon_filepath = path_join(DATA_DIR, lexicon_filename)
    try:
        with open(lexicon_filepath, "rb") as file:
            lexicon = load(file)
        debug("lexicon loaded from %s" % lexicon_filepath)
    except FileNotFoundError:
        train_filepath = path_join(DATA_DIR, train_filename)
        n_lines, lexicon = create_lexicon([train_filepath])  # 10 minutes
        debug("lexicon created from %s" % train_filepath)
    with open(lexicon_filepath, "wb") as pickle_file:
        dump(lexicon, pickle_file)
    debug("lexicon dumped to %s" % pickle_file)
    return lexicon


def unpickle_processed_data():
    with open(pickle_filepath, "rb") as file:
        design_matrix = load(file)
    x_train, y_train, x_test, y_test = design_matrix
    return x_train, y_train, x_test, y_test
